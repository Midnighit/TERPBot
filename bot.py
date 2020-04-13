# bot.py
import os
import re
import random
import config
import logging
import discord
from logging.handlers import RotatingFileHandler
from sqlalchemy import create_engine, or_, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
from discord import utils, DiscordException, ChannelType, Member, Guild, Message
from discord.ext import commands
from discord.ext.commands import command, check
from valve import rcon
from google_api import sheets

bot = commands.Bot(config.PREFIX)
logger = logging.getLogger(__name__)

################
''' SQlite '''
################

# setup the metadata
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    SteamID64 = Column(String(17), unique=True, nullable=False)
    disc_user = Column(String, unique=True, nullable=False)

    def __repr__(self):
        return f"<User(SteamID64='{self.SteamID64}', disc_user='{self.disc_user}')>"

# create the User table
engineUser = create_engine('sqlite:///users.db')
Base.metadata.create_all(engineUser)

# create the User table session
SessionUser = sessionmaker(bind=engineUser)
sessionUser = SessionUser()

class Characters(Base):
    __tablename__ = 'characters'
    playerId = Column(String, primary_key=True)
    id = Column(Integer, nullable=False)
    char_name = Column(String, nullable=False)
    level = Column(Integer)
    rank = Column(Integer)
    guild = Column(Integer)
    isAlive = Column(Boolean)
    killerName = Column(String)
    lastTimeOnline = Column(Integer)
    killerId = Column(String)
    lastServerTimeOnline = Column(Float)

    def __repr__(self):
        return f"<Characters(playerId='{self.playerId}', id='{self.id}', char_name='{self.char_name}', level='{self.level}', rank='{self.rank}', guild='{self.guild}', isAlive='{self.isAlive}', killerName='{self.killerName}', lastTimeOnline='{self.lastTimeOnline}', killerId='{self.killerId}', lastServerTimeOnline='{self.lastServerTimeOnline}')>"

engineGame = create_engine(config.GAME_DB_PATH)
SessionGame = sessionmaker(bind=engineGame)

########################
''' Helper functions '''
########################

async def send_question(author, id, msg=''):
    await author.dm_channel.send(f"{msg}\n__**Question {id + 1} of {len(config.QUESTIONS)}:**__\n> {parse(author, config.QUESTIONS[id])}")

async def send_overview(author, msg='', submitted=False):
    channel = config.CHANNEL[config.APPLICATIONS] if submitted else author.dm_channel
    if len(config.APL[author]['answers']) == 0:
        await channel.send("No questions answered yet!" + msg)
        return
    buffer = ''
    for id in range(len(config.QUESTIONS)):
        if id in config.APL[author]['answers']:
            if len(buffer) + 21 + len(parse(author, config.QUESTIONS[id])) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += f"__**Question {id + 1}:**__\n> {parse(author, config.QUESTIONS[id])}\n"
            if len(buffer) + len(config.APL[author]['answers'][id]) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += config.APL[author]['answers'][id] + "\n"
    if msg and len(buffer) + len(msg) > 2000:
        await channel.send(buffer)
        await channel.send(msg)
    elif msg:
        await channel.send(buffer + msg)
    else:
        await channel.send(buffer)

async def whitelist_player(SteamID64, player, channel):
    try:
        msg = rcon.execute((config.RCON_IP, config.RCON_PORT), config.RCON_PASSWORD, f"WhitelistPlayer {SteamID64}")
        success = True if msg == f"Player {SteamID64} added to whitelist." else False
        if success:
            # If either SteamID64 or disc_user already exist, delete them first
            sessionUser.query(User).filter(or_(User.SteamID64==SteamID64, User.disc_user==str(player))).delete()
            # Store SteamID64 <-> Discord Name link in db
            sessionUser.add(User(SteamID64=SteamID64, disc_user=str(player)))
            sessionUser.commit()
            print(msg)
            await channel.send(msg)
            logger.info(msg)
            return 'yes'
        elif msg.find("Invalid argument") >= 0:
            print(f"Whitelisting failed ({msg}).")
            logger.info(f"Whitelisting failed ({msg}).")
            await channel.send("Whitelisting failed.")
            return 'no'
        else:
            config.WHITELIST[SteamID64] = {'player': player, 'channel': channel}
            print(f"Whitelisting failed ({msg}). Trying again after next restart.")
            logger.info(f"Whitelisting failed ({msg}). Trying again after next restart.")
            await channel.send("Whitelisting failed. Trying again after next restart.")
            return 'delayed'
    except Exception as e:
        config.WHITELIST[SteamID64] = {'player': player, 'channel': channel}
        print(f"Whitelisting failed ({e}). Trying again after next restart.")
        logger.error(f"Whitelisting failed ({e}). Trying again after next restart.")
        await channel.send(f"Whitelisting failed. Trying again after next restart.")
        return 'delayed'

async def find_last_applicant(ctx):
    async for message in ctx.channel.history(limit=100):
        if message.author == bot.user:
            pos_end = message.content.find(" has filled out the application. You can now either")
            if pos_end < 0:
                continue
            pos_start = message.content.rfind("\n", 0, pos_end) + 1
            return message.content[pos_start:pos_end]
    return None

async def roll_dice(dice):
    dice = dice.replace(" ","").split("+")
    val = 0
    lst = []
    for die in dice:
        if die.isnumeric():
            val += int(die)
        else:
            try:
                rolls, limit = map(int, die.split('d'))
            except Exception:
                return None
            lst += [random.randint(1, limit) for r in range(rolls)]
    result = "**" + "**, **".join([str(r) for r in lst]) + "**"
    result = rreplace(result, ",", " and", 1)
    result = result + " + **" + str(val) + "**" if val > 0 else result
    result = f"{result} (total: **{sum(lst) + val}**)" if len(lst) > 1 or val > 0 else result
    return result

def find_steamID64(author):
    result = re.search(r'(7\d{16})', config.APL[author]['answers'][config.STEAMID_QUESTION])
    result = result.group(1) if result else None
    return result

def get_char(SteamID64):
    sessionGame = SessionGame()
    results = sessionGame.query(Characters.playerId, Characters.char_name, Characters.lastTimeOnline).filter(Characters.playerId.like(SteamID64 + '%')).order_by(Characters.playerId).all()
    sessionGame.close()
    lst = []
    for row in results:
        slot = str(row[0])[17] if len(str(row[0])) == 18 else 'active'
        lst.append({'name': str(row[1]), 'slot': slot, 'lastLogin': datetime.utcfromtimestamp(row[2]).strftime("%d-%b-%Y %H:%M:%S UTC")})
    return lst

def get_disc_user(SteamID64):
        result = sessionUser.query(User.disc_user).filter_by(SteamID64=SteamID64).first()
        return result[0] if result else None

def get_steamID64(arg):
    if type(arg) is Member:
        result = sessionUser.query(User.SteamID64).filter_by(disc_user=str(arg)).first()
        return result[0] if result else None
    else:
        sessionGame = SessionGame()
        result = sessionGame.query(Characters.playerId).filter_by(char_name=arg).first()
        sessionGame.close()
        if result:
            return result[0] if len(result[0]) == 17 else result[0][:-1]

def update_questions():
    config.QUESTIONS = [value[0] for value in sheets.read(config.SPREADSHEET_ID, config.QUESTIONS_RANGE)]
    config.GREETING = sheets.read(config.SPREADSHEET_ID, config.GREETING_RANGE)[0][0]
    config.APPLIED = sheets.read(config.SPREADSHEET_ID, config.APPLIED_RANGE)[0][0]
    config.FINISHED =sheets.read(config.SPREADSHEET_ID, config.FINISHED_RANGE)[0][0]
    config.COMMITED = sheets.read(config.SPREADSHEET_ID, config.COMMITED_RANGE)[0][0]
    config.ACCEPTED = sheets.read(config.SPREADSHEET_ID, config.ACCEPTED_RANGE)[0][0]
    config.REJECTED = sheets.read(config.SPREADSHEET_ID, config.REJECTED_RANGE)[0][0]
    config.REVIEWED = sheets.read(config.SPREADSHEET_ID, config.REVIEWED_RANGE)[0][0]
    config.WHITELISTING_FAILED = sheets.read(config.SPREADSHEET_ID, config.WHITELISTING_FAILED_RANGE)[0][0]
    config.WHITELISTING_DELAYED = sheets.read(config.SPREADSHEET_ID, config.WHITELISTING_DELAYED_RANGE)[0][0]
    config.WHITELISTING_SUCCEEDED = sheets.read(config.SPREADSHEET_ID, config.WHITELISTING_SUCCEEDED_RANGE)[0][0]
    config.APP_CLOSED = sheets.read(config.SPREADSHEET_ID, config.APP_CLOSED_RANGE)[0][0]

def find_next_unanswered(author):
    if len(config.APL[author]['answers']) >= len(config.QUESTIONS):
        return -1
    for id in range(len(config.QUESTIONS)):
        if id not in config.APL[author]['answers']:
            return id
    return -1

def parse(author, msg):
    msg = str(msg).replace('{PREFIX}', config.PREFIX) \
                  .replace('{OWNER}', config.GUILD.owner.mention) \
                  .replace('{PLAYER}', author.mention)
    for name, channel in config.CHANNEL.items():
        msg = re.sub("(?i){" + name + "}", channel.mention, msg)
    for name, role in config.ROLE.items():
        msg = re.sub("(?i){" + name + "}", role.mention, msg)
    return msg

def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)

##############
''' Checks '''
##############

async def is_applicant(ctx):
    return ctx.author in config.APL

async def is_not_applicant(ctx):
    return not ctx.author in config.APL

async def is_private(ctx):
    return ctx.channel.type == ChannelType.private

async def is_not_bot(ctx):
    return ctx.author != bot.user

def has_role_greater_or_equal(check_role: str):
    async def predicate(ctx):
        member = config.GUILD.get_member(ctx.author.id)
        for author_role in member.roles:
            if author_role >= config.ROLE[check_role]:
                return True
        return False
    return commands.check(predicate)

def has_role_greater(check_role: str):
    async def predicate(ctx):
        member = config.GUILD.get_member(ctx.author.id)
        for author_role in member.roles:
            if author_role > config.ROLE[check_role]:
                return True
        return False
    return commands.check(predicate)

##############
''' Events '''
##############

@bot.event
async def on_ready():
    # enable logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    err_handler = RotatingFileHandler('logs/error.log', maxBytes=10240, backupCount=10)
    err_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    err_handler.setLevel(logging.ERROR)
    logger.addHandler(err_handler)
    file_handler = RotatingFileHandler('logs/bot.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.setLevel(config.LOG_LEVEL)
    logger.addHandler(file_handler)
    rcon.RCONMessage.ENCODING = "utf-8"
    print(f"{bot.user.name} has connected to Discord.")
    logger.info(f"{bot.user.name} has connected to Discord.")
    config.APL = config.WHITELIST = {}
    # determine discord server
    config.GUILD = discord.utils.get(bot.guilds, name=config.DISCORD_NAME)
    if config.GUILD:
        print(f"Discord server {config.GUILD.name} ({config.GUILD.id}) was found.")
    else:
        exit(f"{config.DISCORD_NAME} wasn't found. Please check config.py or authorize the bot.")
    # get all categories
    config.CATEGORY = {}
    for category in config.GUILD.categories:
        config.CATEGORY[category.name] = category
    # get all channels
    config.CHANNEL = {}
    for channel in config.GUILD.channels:
        config.CHANNEL[channel.name] = channel
    # get all roles
    config.ROLE = {}
    for role in config.GUILD.roles:
        config.ROLE[role.name] = role
    # create channel and category if necessary
    for channel in config.DISCORD_CHANNELS:
        if not channel[0] in config.CHANNEL:
            config.CHANNEL[channel[0]] = await config.GUILD.create_text_channel(channel[0], category=channel[1])
            print(f"{channel[0]} channel was created (id = {config.CHANNEL[channel[0]].id})")
    # read questions from google sheet
    update_questions()
    # initialize randomizer
    random.seed()

@bot.event
async def on_member_join(member):
    logger.info(f"{member} just joined the discord.")
    await member.edit(roles=member.roles + [config.ROLE[config.NOT_APPLIED_ROLE]])
    await config.CHANNEL[config.WELCOME].send(parse(member, config.GREETING))

@bot.event
async def on_message(message):
    if message.content.find("Server The Exiled RP-PvP is Ready:") >= 0:
        for SteamID64, data in config.WHITELIST.items():
            await whitelist_player(SteamID64, data['player'], data['channel'])
        return
    if not message.channel.type == ChannelType.private or not message.author in config.APL:
        await bot.process_commands(message)
        return
    if message.content[0] == config.PREFIX:
        word = message.content.split(None, 1)[0][1:]
        for command in bot.commands:
            if command.name == word:
                await bot.process_commands(message)
                return
    if not config.APL[message.author]['open']:
        await message.author.dm_channel.send(parse(message.author, config.APP_CLOSED))
        return
    if config.APL[message.author]['questionId'] < 0:
        return
    config.APL[message.author]['answers'][config.APL[message.author]['questionId']] = message.content
    questionId = find_next_unanswered(message.author)
    if questionId >= 0:
        await send_question(message.author, questionId)
    elif not config.APL[message.author]['finished']:
        config.APL[message.author]['finished'] = True
        await message.author.dm_channel.send(parse(message.author, config.FINISHED))
    config.APL[message.author]['questionId'] = questionId

####################
''' Bot commands '''
####################

class Applications(commands.Cog, name="Application commands"):
    @command(name='apply', help="Starts the application process")
    @check(is_not_applicant)
    async def apply(self, ctx):
        await ctx.author.create_dm()
        await send_question(ctx.author, 0, msg=parse(ctx.author, config.APPLIED))
        await config.CHANNEL[config.APPLICATIONS].send(f"{ctx.author} has started an application.")
        print(f"{ctx.author} has started an application.")
        config.APL[ctx.author] = \
            {'timestamp': datetime.utcnow(), 'finished': False, 'open': True, 'questionId': 0, 'answers': {}}

    @apply.error
    async def applicant_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            if config.APL[ctx.author]['finished']:
                msg = f"You already have an open application and all questions have been answered. You can review them with `{config.PREFIX}overview` and use `{config.PREFIX}submit` to finish the application and send it to the admins."
                await ctx.author.dm_channel.send(msg)
            else:
                msg = f"You already have an open application."
                await send_question(ctx.author, config.APL[ctx.author]['questionId'], msg=msg)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Question number must be between 1 and {len(config.QUESTIONS)}")
        else:
            await ctx.send(error)
            logger.error(error)

    @command(name='question', help="Used to switch to a given question. If no number is given, repeats the current question")
    @check(is_applicant)
    @check(is_private)
    async def question(self, ctx, number=None):
        if not config.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, config.APP_CLOSED))
            return
        if number is None:
            if config.APL[ctx.author]['questionId'] < 0:
                await ctx.author.dm_channel.send(parse(ctx.author, config.FINISHED))
                return
            await send_question(ctx.author, config.APL[ctx.author]['questionId'])
            return
        if not number.isnumeric() or int(number) < 1 or int(number) > len(config.QUESTIONS):
            raise commands.BadArgument
        await send_question(ctx.author, int(number) - 1)
        config.APL[ctx.author]['questionId'] = int(number) - 1

    @command(name='overview', help="Display all questions that have already been answered")
    @check(is_applicant)
    async def overview(self, ctx):
        await send_overview(ctx.author)

    @command(name='submit', help="Submit your application and send it to the admins")
    @check(is_applicant)
    async def submit(self, ctx):
        if len(config.QUESTIONS) > len(config.APL[ctx.author]['answers']):
            await ctx.author.dm_channel.send("Please answer all questions first.")
            return
        if not config.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, config.APP_CLOSED))
            return
        config.APL[ctx.author]['open'] = False
        await ctx.author.dm_channel.send(parse(ctx.author, config.COMMITED))
        print(f"{ctx.author} has submitted their application.")
        msg = f"{ctx.author} has filled out the application. You can now either \n`{config.PREFIX}accept <applicant> <message>`, `{config.PREFIX}reject <applicant> <message>` or `{config.PREFIX}review <applicant> <message>` (asking the applicant to review their answers) it.\nIf <message> is omitted a default message will be sent.\nIf <applicant> is also omitted, it will try to target the last application."
        await send_overview(ctx.author, msg=msg, submitted=True)

    @command(name='cancel', help="Cancel your application")
    @check(is_applicant)
    async def cancel(self, ctx):
        await config.CHANNEL[config.APPLICATIONS].send(f"{ctx.author} has canceled their application.")
        await ctx.author.dm_channel.send("Your application has been canceled.")
        print(f"{ctx.author} has canceled their application.")
        del config.APL[ctx.author]

    @question.error
    @overview.error
    @submit.error
    @cancel.error
    async def application_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f"You do not have an open application. Start one with `{config.PREFIX}apply`.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Question number must be a number between 1 and {len(config.QUESTIONS)}")
        else:
            await ctx.send(error)
            logger.error(error)

    @command(name='accept', help="Accept the application. If message is ommitted a default message will be sent. If message and applicant are omitted target the last submitted application.")
    @commands.has_role(config.ADMIN_ROLE)
    async def accept(self, ctx, applicant=None, *message):
        # if no applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await find_last_applicant(ctx)
            if applicant is None:
                config.CHANNEL[config.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the applicant via `{config.PREFIX}accept <applicant>`.")
                return
        applicant = await commands.MemberConverter().convert(ctx, applicant)
        # confirm that there is a closed application for that applicant
        if not applicant in config.APL or config.APL[applicant]['open']:
            await config.CHANNEL[config.APPLICATIONS].send(f"Couldn't find a submitted application for {applicant}. Please verify that the name is written correctly and try again.")
        # remove Not Applied role
        if message:
            message = " ".join(message)
        if config.ROLE[config.NOT_APPLIED_ROLE] in applicant.roles:
            new_roles = applicant.roles
            new_roles.remove(config.ROLE[config.NOT_APPLIED_ROLE])
            await applicant.edit(roles=new_roles)
        # Whitelist applicant
        SteamID64 = find_steamID64(applicant)
        if SteamID64:
            result = await whitelist_player(SteamID64, applicant, config.CHANNEL[config.APPLICATIONS])
        else:
            result = 'no'
            logger.info(f"Whitelisting {applicant} failed. No SteamID64 found in answer [{config.APL[ctx.author]['answers'][config.STEAMID_QUESTION]}].")
            await config.CHANNEL[config.APPLICATIONS].send(f"Whitelisting {applicant} failed. No SteamID64 found in answer [{config.APL[ctx.author]['answers'][config.STEAMID_QUESTION]}].")
        # Send feedback to applications channel and to applicant
        await config.CHANNEL[config.APPLICATIONS].send(f"{applicant}'s application has been accepted.")
        if not message:
            message = parse(ctx.author, config.ACCEPTED)
        if result == 'yes':
            await applicant.dm_channel.send("Your application was accepted:\n" + message + "\n" + parse(ctx.author, config.WHITELISTING_SUCCEEDED))
        elif result == 'delayed':
            await applicant.dm_channel.send("Your application was accepted:\n" + message + "\n" + parse(ctx.author, config.WHITELISTING_DELAYED))
        else:
            await applicant.dm_channel.send("Your application was accepted:\n" + message + "\n" + parse(ctx.author, config.WHITELISTING_FAILED))
        # remove application from list of open applications
        del config.APL[applicant]
        print(f"{ctx.author} has accepted {applicant}'s application.")

    @command(name='reject', help="Reject the application. If message is omitted a default message will be sent. If message and applicant are omitted target the last submitted application.")
    @commands.has_role(config.ADMIN_ROLE)
    async def reject(self, ctx, applicant=None, *message):
        # if no applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await find_last_applicant(ctx)
            if applicant is None:
                config.CHANNEL[config.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the applicant via `{config.PREFIX}reject <applicant> <message>`.")
                return
        applicant = await commands.MemberConverter().convert(ctx, applicant)
        # confirm that there is a closed application for that applicant
        if not applicant in config.APL or config.APL[applicant]['open']:
            await config.CHANNEL[config.APPLICATIONS].send(f"Couldn't find a submitted application for {applicant}. Please verify that the name is written correctly and try again.")
        # Send feedback to applications channel and to applicant
        await config.CHANNEL[config.APPLICATIONS].send(f"{applicant}'s application has been rejected.")
        if not message:
            await applicant.dm_channel.send(parse(ctx.author, "Your application was rejected:\n" + config.REJECTED))
        else:
            await applicant.dm_channel.send("Your application was rejected:\n" + " ".join(message))
        # remove application from list of open applications
        del config.APL[applicant]
        print(f"{ctx.author} has rejected {applicant}'s application.")

    @command(name='review', help="Ask the applicant to review their application. If message is omitted a default message will be sent. If message and applicant are omitted target the last submitted application.")
    @commands.has_role(config.ADMIN_ROLE)
    async def review(self, ctx, applicant=None, *message):
        # if no applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await find_last_applicant(ctx)
            if applicant is None:
                await config.CHANNEL[config.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the applicant via `{config.PREFIX}review <applicant> <message>`.")
                return
        applicant = await commands.MemberConverter().convert(ctx, applicant)
        # confirm that there is a closed application for that applicant
        if not applicant in config.APL or config.APL[applicant]['open']:
            await config.CHANNEL[config.APPLICATIONS].send(f"Couldn't find a submitted application for {applicant}. Please verify that the name is written correctly and try again.")
            return
        # Send feedback to applications channel and to applicant
        await config.CHANNEL[config.APPLICATIONS].send(f"{applicant}'s application has been returned.")
        explanation = f"\nYou can change the answer to any question by going to that question with `{config.PREFIX}question <number>` and then writing your new answer.\nYou can always review your current answers by entering `{config.PREFIX}overview`."
        if not message:
            await send_overview(applicant, "Your application was returned to you for review:\n" + config.REVIEWED + explanation)
        else:
            await send_overview(applicant, "Your application was returned to you for review:\n" + " ".join(message) + explanation)
        # remove application from list of open applications
        config.APL[applicant]['open'] = True
        print(f"{ctx.author} has returned {applicant}'s application.")

    @command(name='showapp', help="Displays the given applicants application if it has been submitted. When applicant is omitted, shows all applications.")
    @commands.has_role(config.ADMIN_ROLE)
    async def showapp(self, ctx, *, applicant=None):
        if applicant:
            applicant = await commands.MemberConverter().convert(ctx, applicant)
            if not applicant in config.APL:
                await ctx.channel.send(f"No application for {applicant} found")
            elif config.APL[applicant]['open']:
                await ctx.channel.send("Can't access application while it's still being worked on.")
            else:
                await send_overview(ctx.author, submitted=True)
            return
        else:
            msg = "" if len(config.APL) > 0 else "No open applications right now."
            for applicant, aplication in config.APL.items():
                msg += f"Applicant {applicant} is {'still working on their application' if aplication['open'] else 'waiting for admin approval'}.\n"
            if len(config.APL) > 0:
                msg += f"You can view a specific application by entering `{config.PREFIX}showapp <applicant>`."
            await ctx.channel.send(msg)
            return

    @command(name='cancelapp', help="Displays the given applicants application if it has been submitted. When applicant is omitted, shows all applications.")
    @commands.has_role(config.ADMIN_ROLE)
    async def cancelapp(self, ctx, applicant, *message):
        applicant = await commands.MemberConverter().convert(ctx, applicant)
        if not applicant in config.APL:
            await ctx.channel.send(f"Applicant {applicant} couldn't be found.")
            return
        del config.APL[applicant]
        if message:
            message = " ".join(message)
        await ctx.channel.send(f"Application for {applicant} has been cancelled.")
        await applicant.dm_channel.send(f"Your application was cancelled by an administrator.{' Message: ' + message + '.' if len(message) > 0 else ''}")
        print(f"Application for {applicant} has been cancelled.")

    @command(name='reloadsheets', help="Updates all default messages and questions from google sheets.")
    @commands.has_role(config.ADMIN_ROLE)
    async def reloadsheets(self, ctx):
        update_questions()
        await ctx.channel.send("Default messages and questions have been reloaded from google sheets.")

    @accept.error
    @reject.error
    @review.error
    @showapp.error
    @cancelapp.error
    @reloadsheets.error
    async def not_admin_error(self, ctx, error):
        print(f"not_admin_error: {error}")
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f"You do not have the required permissions ({error})")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Applicant couldn't be found")
        else:
            await ctx.send(error)
            logger.error(error)

class RCon(commands.Cog, name="RCon commands"):
    @command(name='listplayers', help="Shows a list of all players online right now")
    async def listplayers(self, ctx):
        playerlist = rcon.execute((config.RCON_IP, config.RCON_PORT), config.RCON_PASSWORD, "ListPlayers")
        lines = playerlist.split('\n')
        names = []
        headline = True
        for line in lines:
            if headline:
                headline = False
            else:
                columns = line.split('|')
                if len(columns) >= 2:
                    names.append(columns[1].strip())
        num = len(names)
        if num == 0:
            await ctx.send("Nobody is currently online")
        elif num < 20:
            await ctx.send(f"__**Players online:**__ {len(names)}\n" + '\n'.join(names))
        else:
            await ctx.send(rreplace(f"__**Players online:**__ {len(names)}\n" + ', '.join(names), ",", " and", 1))

    @listplayers.error
    async def listplayers_error(self, ctx, error):
        await ctx.send("Error: something went wrong with the command. Please try again later or contact an administrator.")
        logger.error(error)
        
    @command(name='whitelist', help="Whitelists the player with the given discord nick and SteamID64")
    @commands.has_role(config.ADMIN_ROLE)
    async def whitelist(self, ctx, player: Member, SteamID64: int):
        await whitelist_player(SteamID64, player, ctx.channel)

    @whitelist.error
    async def whitelist_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("SteamID64 must be a 17 digits number")
        else:
            await ctx.send(error)
            logger.error(error)

class General(commands.Cog, name="General commands"):
    @command(name='roll', help="Rolls a dice in NdN format")
    async def roll(self, ctx, *, dice: str):
        result = await roll_dice(dice)
        if not result:
            await ctx.send("Format needs to be in XdY+Z format. (e.g. 1d20 + 3d4 + 4)" )
        await ctx.send(f"{ctx.author.mention} rolled: " + result)

    @roll.error
    async def roll_error(self, ctx, error):
        await ctx.send(error)
        logger.error(error)

    @command(name="setsteamid", help="Set your 17 digit SteamID64 (the one used to whitelist you)")
    @has_role_greater(config.NOT_APPLIED_ROLE)
    async def setsteamid(self, ctx, SteamID64: str):
        if not SteamID64.isnumeric() or len(SteamID64) != 17:
            raise DiscordException("SteamID64 must be a 17 digits number")
        sessionUser.query(User).filter(or_(User.SteamID64==SteamID64, User.disc_user==str(ctx.author))).delete()
        sessionUser.add(User(SteamID64=SteamID64, disc_user=str(ctx.author)))
        sessionUser.commit()
        logger.info(f"Player {ctx.author} set their SteamID64 to {SteamID64}.")
        await ctx.channel.send(f"Your SteamID64 has been set to {SteamID64}.")

    @setsteamid.error
    async def setsteamid_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the permission to use this command")
        else:
            await ctx.send(error)
            logger.error(error)

    @command(name="whois", help="Tells you the chararacter name(s) belonging to the given discord user or vice versa")
    @has_role_greater_or_equal(config.SUPPORT_ROLE)
    async def whois(self, ctx, *, arg):
        try:
            disc_user = await commands.MemberConverter().convert(ctx, arg)
        except:
            disc_user = None
        msg = f"The characters belonging to the discord nick **{disc_user}** are:\n"
        if disc_user:
            SteamID64 = get_steamID64(disc_user)
            if SteamID64:
                characters = get_char(SteamID64)
                if characters:
                    for char in characters:
                        if char['slot'] == 'active':
                            msg += f"**{char['name']}** on active slot (last login: {char['lastLogin']})\n"
                        else:
                            msg += f"**{char['name']}** on slot {char['slot']} (last login: {char['lastLogin']})\n"
                else:
                    msg = "No character belonging to that discord nick has been found."
            else:
                msg = "No character belonging to that discord nick has been found."
        else:
            SteamID64 = get_steamID64(arg)
            if SteamID64:
                disc_user = get_disc_user(SteamID64)
                if disc_user:
                    msg = f"The discord nick of the player of {arg} is **{disc_user}**"
                else:
                    msg = f"No discord nick associated with that character has been found"
            else:
                msg = f"No character named {arg} has been found"
        await ctx.channel.send(msg)

    @whois.error
    async def whois_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the permission to use this command")
        await ctx.send(error)
        logger.error(error)

bot.add_cog(Applications())
bot.add_cog(RCon())
bot.add_cog(General())
bot.run(config.DISCORD_TOKEN)
