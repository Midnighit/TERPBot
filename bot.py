# bot.py
import os
import re
import random
import logging
import discord
import config as cfg
import exceptions as exc
from checks import is_applicant, is_not_applicant, has_role, has_not_role, has_role_greater_or_equal, number_in_range
from logging.handlers import RotatingFileHandler
from sqlalchemy import create_engine, func, or_, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
from discord import utils, ChannelType, Member, Guild, Message
from discord.ext import commands
from discord.ext.commands import command
from valve import rcon
from google_api import sheets

bot = commands.Bot(cfg.PREFIX)
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

engineGame = create_engine(cfg.GAME_DB_PATH)
SessionGame = sessionmaker(bind=engineGame)

########################
''' Helper functions '''
########################

async def send_question(author, id, msg=''):
    await author.dm_channel.send(f"{msg}\n__**Question {id + 1} of {len(cfg.QUESTIONS)}:**__\n> {parse(author, cfg.QUESTIONS[id])}")

async def send_overview(author, msg='', submitted=False):
    channel = cfg.CHANNEL[cfg.APPLICATIONS] if submitted else author.dm_channel
    if len(cfg.APL[author]['answers']) == 0:
        await channel.send("No questions answered yet!" + msg)
        return
    buffer = ''
    for id in range(len(cfg.QUESTIONS)):
        if id in cfg.APL[author]['answers']:
            if len(buffer) + 21 + len(parse(author, cfg.QUESTIONS[id])) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += f"__**Question {id + 1}:**__\n> {parse(author, cfg.QUESTIONS[id])}\n"
            if len(buffer) + len(cfg.APL[author]['answers'][id]) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += cfg.APL[author]['answers'][id] + "\n"
    if msg and len(buffer) + len(msg) > 2000:
        await channel.send(buffer)
        await channel.send(msg)
    elif msg:
        await channel.send(buffer + msg)
    else:
        await channel.send(buffer)

async def whitelist_player(ctx, SteamID64, player):
    SteamID64 = str(SteamID64)
    if len(SteamID64) != 17 or not SteamID64.isnumeric():
        return "NotSteamIdError"
    elif SteamID64 == "76561197960287930":
        return "IsGabesIDError"
    try:
        msg = rcon.execute((cfg.RCON_IP, cfg.RCON_PORT), cfg.RCON_PASSWORD, f"WhitelistPlayer {SteamID64}")
    except:
        with open(cfg.WHITELIST_PATH, 'r') as f:
            lines = f.readlines()
            line = SteamID64 + "\n" if lines[-1][-1] == "\n" else "\n" + SteamID64 + "\n"
        with open(cfg.WHITELIST_PATH, 'a') as f:
            f.write(line)
        msg = f"Player {SteamID64} added to whitelist."
    success = True if msg == f"Player {SteamID64} added to whitelist." else False
    if success:
        # If either SteamID64 or disc_user already exist, delete them first
        sessionUser.query(User).filter(or_(User.SteamID64==SteamID64, User.disc_user==str(player))).delete()
        # Store SteamID64 <-> Discord Name link in db
        sessionUser.add(User(SteamID64=SteamID64, disc_user=str(player)))
        sessionUser.commit()
        return msg
    elif msg.find("Invalid argument") >= 0:
        return f"FailedError|{msg}"

async def find_last_Applicant(ctx):
    async for message in ctx.channel.history(limit=100):
        if message.author == bot.user:
            pos_end = message.content.find(" has filled out the application. You can now either")
            if pos_end < 0:
                continue
            pos_start = message.content.rfind("\n", 0, pos_end) + 1
            return message.content[pos_start:pos_end]
    return None

async def roll_dice(dice):
    if dice.find('d') == -1:
        raise exc.NoDiceFormatError()
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
                raise exc.NoDiceFormatError()
            lst += [random.randint(1, limit) for r in range(rolls)]
    result = "**" + "**, **".join([str(r) for r in lst]) + "**"
    result = rreplace(result, ",", " and", 1)
    result = result + " + **" + str(val) + "**" if val > 0 else result
    result = f"{result} (total: **{sum(lst) + val}**)" if len(lst) > 1 or val > 0 else result
    return result

def find_steamID64(author):
    result = re.search(r'(7\d{16})', cfg.APL[author]['answers'][cfg.STEAMID_QUESTION])
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
        result = sessionGame.query(Characters.playerId).filter(func.lower(Characters.char_name)==arg.lower()).first()
        sessionGame.close()
        if result:
            return result[0] if len(result[0]) == 17 else result[0][:-1]

def update_questions():
    cfg.QUESTIONS = [value[0] for value in sheets.read(cfg.SPREADSHEET_ID, cfg.QUESTIONS_RANGE)]
    cfg.GREETING = sheets.read(cfg.SPREADSHEET_ID, cfg.GREETING_RANGE)[0][0]
    cfg.APPLIED = sheets.read(cfg.SPREADSHEET_ID, cfg.APPLIED_RANGE)[0][0]
    cfg.FINISHED =sheets.read(cfg.SPREADSHEET_ID, cfg.FINISHED_RANGE)[0][0]
    cfg.COMMITED = sheets.read(cfg.SPREADSHEET_ID, cfg.COMMITED_RANGE)[0][0]
    cfg.ACCEPTED = sheets.read(cfg.SPREADSHEET_ID, cfg.ACCEPTED_RANGE)[0][0]
    cfg.REJECTED = sheets.read(cfg.SPREADSHEET_ID, cfg.REJECTED_RANGE)[0][0]
    cfg.REVIEWED = sheets.read(cfg.SPREADSHEET_ID, cfg.REVIEWED_RANGE)[0][0]
    cfg.WHITELISTING_FAILED = sheets.read(cfg.SPREADSHEET_ID, cfg.WHITELISTING_FAILED_RANGE)[0][0]
    cfg.WHITELISTING_SUCCEEDED = sheets.read(cfg.SPREADSHEET_ID, cfg.WHITELISTING_SUCCEEDED_RANGE)[0][0]
    cfg.APP_CLOSED = sheets.read(cfg.SPREADSHEET_ID, cfg.APP_CLOSED_RANGE)[0][0]

def find_next_unanswered(author):
    if len(cfg.APL[author]['answers']) >= len(cfg.QUESTIONS):
        return -1
    for id in range(len(cfg.QUESTIONS)):
        if id not in cfg.APL[author]['answers']:
            return id
    return -1

def parse(author, msg):
    msg = str(msg).replace('{PREFIX}', cfg.PREFIX) \
                  .replace('{OWNER}', cfg.GUILD.owner.mention) \
                  .replace('{PLAYER}', author.mention)
    for name, channel in cfg.CHANNEL.items():
        msg = re.sub("(?i){" + name + "}", channel.mention, msg)
    for name, role in cfg.ROLE.items():
        msg = re.sub("(?i){" + name + "}", role.mention, msg)
    return msg

def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)

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
    logger.setLevel(cfg.LOG_LEVEL)
    logger.addHandler(file_handler)
    rcon.RCONMessage.ENCODING = "utf-8"
    print(f"{bot.user.name} has connected to Discord.")
    logger.info(f"{bot.user.name} has connected to Discord.")
    cfg.APL = {}
    cfg.caught = False
    # determine discord server
    cfg.GUILD = discord.utils.get(bot.guilds, name=cfg.DISCORD_NAME)
    if cfg.GUILD:
        print(f"Discord server {cfg.GUILD.name} ({cfg.GUILD.id}) was found.")
    else:
        exit(f"{cfg.DISCORD_NAME} wasn't found. Please check cfg.py or authorize the bot.")
    # get all categories
    cfg.CATEGORY = {}
    for category in cfg.GUILD.categories:
        cfg.CATEGORY[category.name] = category
    # get all channels
    cfg.CHANNEL = {}
    for channel in cfg.GUILD.channels:
        cfg.CHANNEL[channel.name] = channel
    # get all roles
    cfg.ROLE = {}
    for role in cfg.GUILD.roles:
        cfg.ROLE[role.name] = role
    # create channel and category if necessary
    for channel in cfg.DISCORD_CHANNELS:
        if not channel[0] in cfg.CHANNEL:
            cfg.CHANNEL[channel[0]] = await cfg.GUILD.create_text_channel(channel[0], category=channel[1])
            print(f"{channel[0]} channel was created (id = {cfg.CHANNEL[channel[0]].id})")
    # read questions from google sheet
    update_questions()
    # initialize randomizer
    random.seed()

@bot.event
async def on_member_join(member):
    logger.info(f"{member} just joined the discord.")
    await member.edit(roles=member.roles + [cfg.ROLE[cfg.NOT_APPLIED_ROLE]])
    await cfg.CHANNEL[cfg.WELCOME].send(parse(member, cfg.GREETING))

@bot.event
async def on_message(message):
    if not message.channel.type == ChannelType.private or not message.author in cfg.APL:
        await bot.process_commands(message)
        return
    if message.content[0] == cfg.PREFIX:
        word = message.content.split(None, 1)[0][1:]
        for command in bot.commands:
            if command.name == word:
                await bot.process_commands(message)
                return
    if not cfg.APL[message.author]['open']:
        await message.author.dm_channel.send(parse(message.author, cfg.APP_CLOSED))
        return
    if cfg.APL[message.author]['questionId'] < 0:
        return
    cfg.APL[message.author]['answers'][cfg.APL[message.author]['questionId']] = message.content
    questionId = find_next_unanswered(message.author)
    if questionId >= 0:
        await send_question(message.author, questionId)
    elif not cfg.APL[message.author]['finished']:
        cfg.APL[message.author]['finished'] = True
        await message.author.dm_channel.send(parse(message.author, cfg.FINISHED))
    cfg.APL[message.author]['questionId'] = questionId

@bot.event
async def on_command_error(ctx, error):
    if cfg.caught:
        cfg.caught = False
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("Bad argument error.")
    elif isinstance(error, commands.CommandError):
        await ctx.send(error)
    else:
        await ctx.send("Unknown error. Please check the logs for details.")
    f = False
    if hasattr(error, "args"):
        for arg in error.args:
            if type(arg) is str:
                error = arg
                f = True
                break
    print(f"ERROR: Author: {ctx.author} / Command: {ctx.message.content}. {str(error)}")
    logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {str(error)}")

####################
''' Bot commands '''
####################

class Applications(commands.Cog, name="Application commands"):
    @command(name='apply', help="Starts the application process")
    @is_not_applicant()
    async def apply(self, ctx):
        await ctx.author.create_dm()
        await send_question(ctx.author, 0, msg=parse(ctx.author, cfg.APPLIED))
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{ctx.author} has started an application.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")
        cfg.APL[ctx.author] = \
            {'timestamp': datetime.utcnow(), 'finished': False, 'open': True, 'questionId': 0, 'answers': {}}

    @command(name='question', help="Used to switch to a given question. If no number is given, repeats the current question")
    @is_applicant()
    @commands.dm_only()
    async def question(self, ctx, Number=None):
        if not cfg.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, cfg.APP_CLOSED))
            return
        if Number is None:
            if cfg.APL[ctx.author]['questionId'] < 0:
                await ctx.author.dm_channel.send(parse(ctx.author, cfg.FINISHED))
                return
            await send_question(ctx.author, cfg.APL[ctx.author]['questionId'])
            return
        if not Number.isnumeric():
            raise exc.NotNumberError(f"Argument must be a number between 1 and {len(cfg.QUESTIONS)}.")
        if not Number.isnumeric() or int(Number) < 1 or int(Number) > len(cfg.QUESTIONS):
            raise exc.NumberNotInRangeError(f"Number must be between 1 and {len(cfg.QUESTIONS)}.")
        await send_question(ctx.author, int(Number) - 1)
        cfg.APL[ctx.author]['questionId'] = int(Number) - 1

    @command(name='overview', help="Display all questions that have already been answered")
    @is_applicant()
    async def overview(self, ctx):
        await send_overview(ctx.author)

    @command(name='submit', help="Submit your application and send it to the admins")
    @is_applicant()
    async def submit(self, ctx):
        if len(cfg.QUESTIONS) > len(cfg.APL[ctx.author]['answers']):
            await ctx.author.dm_channel.send("Please answer all questions first.")
            return
        if not cfg.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, cfg.APP_CLOSED))
            return
        cfg.APL[ctx.author]['open'] = False
        await ctx.author.dm_channel.send(parse(ctx.author, cfg.COMMITED))
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        msg = f"{ctx.author} has filled out the application. You can now either \n`{cfg.PREFIX}accept <applicant> <message>`, `{cfg.PREFIX}reject <applicant> <message>` or `{cfg.PREFIX}review <applicant> <message>` (asking the Applicant to review their answers) it.\nIf <message> is omitted a default message will be sent.\nIf <applicant> is also omitted, it will try to target the last application."
        await send_overview(ctx.author, msg=msg, submitted=True)

    @command(name='cancel', help="Cancel your application")
    @is_applicant()
    async def cancel(self, ctx):
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{ctx.author} has canceled their application.")
        await ctx.author.dm_channel.send("Your application has been canceled.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")
        del cfg.APL[ctx.author]

    @command(name='accept', help="Accept the application. If message is ommitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def accept(self, ctx, Applicant=None, *Message):
        # if no Applicant is given, try to automatically determine one
        if Applicant is None:
            Applicant = await find_last_Applicant(ctx)
            if Applicant is None:
                await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}accept <applicant>`.")
                return
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        # confirm that there is a closed application for that Applicant
        if not Applicant in cfg.APL or cfg.APL[Applicant]['open']:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {Applicant}. Please verify that the name is written correctly and try again.")
        # remove Not Applied role
        if Message:
            Message = " ".join(Message)
        if cfg.ROLE[cfg.NOT_APPLIED_ROLE] in Applicant.roles:
            new_roles = Applicant.roles
            new_roles.remove(cfg.ROLE[cfg.NOT_APPLIED_ROLE])
            await Applicant.edit(roles=new_roles)

        # Whitelist Applicant
        SteamID64 = find_steamID64(Applicant)
        if SteamID64:
            result = await whitelist_player(ctx, SteamID64, Applicant)
        else:
            result = "NoSteamIDinAnswer"

        # Send feedback about accepting the application
        if not Message:
            Message = parse(ctx.author, cfg.ACCEPTED)
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{Applicant}'s application has been accepted.")
        await Applicant.dm_channel.send("Your application was accepted:\n" + Message)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been accepted.")

        # Send feedback about whitelisting success
        info = parse(ctx.author, "They have been informed to request whitelisting in {SUPPORT-REQUESTS}.")
        if result == "NoSteamIDinAnswer":
            await Applicant.dm_channel.send("Whitelisting failed, you have given no valid SteamID64 your answer. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {Applicant} failed. No valid SteamID64 found in answer:\n> {cfg.APL[ctx.author]['answers'][cfg.STEAMID_QUESTION]}\n{info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
        elif result == "IsGabesIDError" :
            await Applicant.dm_channel.send("Whitelisting failed, you have given the example SteamID64 of Gabe Newell instead of your own. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {Applicant} failed. Applicant gave Gabe Newells SteamID64. {info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. IsGabesIDError")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. IsGabesIDError")
        elif result.find("FailedError") >= 0:
            result = result[12:]
            await Applicant.dm_channel.send("Whitelisting failed. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {Applicant} failed (error message: {result}). {info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
        else:
            await Applicant.dm_channel.send(parse(ctx.author, cfg.WHITELISTING_SUCCEEDED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(result)
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")

        # remove application from list of open applications
        del cfg.APL[Applicant]
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been accepted.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been accepted.")

    @command(name='reject', help="Reject the application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def reject(self, ctx, Applicant=None, *Message):
        # if no Applicant is given, try to automatically determine one
        if Applicant is None:
            Applicant = await find_last_Applicant(ctx)
            if Applicant is None:
                cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}reject <applicant> <message>`.")
                return
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        # confirm that there is a closed application for that Applicant
        if not Applicant in cfg.APL or cfg.APL[Applicant]['open']:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {Applicant}. Please verify that the name is written correctly and try again.")
        # Send feedback to applications channel and to Applicant
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{Applicant}'s application has been rejected.")
        if not Message:
            await Applicant.dm_channel.send(parse(ctx.author, "Your application was rejected:\n" + cfg.REJECTED))
        else:
            await Applicant.dm_channel.send("Your application was rejected:\n" + " ".join(Message))
        # remove application from list of open applications
        del cfg.APL[Applicant]
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been rejected.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been rejected.")

    @command(name='review', help="Ask the Applicant to review their application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def review(self, ctx, Applicant=None, *Message):
        # if no Applicant is given, try to automatically determine one
        if Applicant is None:
            Applicant = await find_last_Applicant(ctx)
            if Applicant is None:
                await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}review <applicant> <message>`.")
                return
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        # confirm that there is a closed application for that Applicant
        if not Applicant in cfg.APL or cfg.APL[Applicant]['open']:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {Applicant}. Please verify that the name is written correctly and try again.")
            return
        # Send feedback to applications channel and to Applicant
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{Applicant}'s application has been returned.")
        explanation = f"\nYou can change the answer to any question by going to that question with `{cfg.PREFIX}question <number>` and then writing your new answer.\nYou can always review your current answers by entering `{cfg.PREFIX}overview`."
        if not Message:
            await send_overview(Applicant, "Your application was returned to you for review:\n" + cfg.REVIEWED + explanation)
        else:
            await send_overview(Applicant, "Your application was returned to you for review:\n" + " ".join(Message) + explanation)
        # remove application from list of open applications
        cfg.APL[Applicant]['open'] = True
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been returned for review.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been returned for review.")

    @command(name='showapp', help="Displays the given Applicants application if it has been submitted. When Applicant is omitted, shows all applications.")
    @has_role(cfg.ADMIN_ROLE)
    async def showapp(self, ctx, *, Applicant=None):
        if Applicant:
            Applicant = await commands.MemberConverter().convert(ctx, Applicant)
            if not Applicant in cfg.APL:
                await ctx.channel.send(f"No application for {Applicant} found")
            elif cfg.APL[Applicant]['open']:
                await ctx.channel.send("Can't access application while it's still being worked on.")
            else:
                await send_overview(ctx.author, submitted=True)
            return
        else:
            msg = "" if len(cfg.APL) > 0 else "No open applications right now."
            for Applicant, aplication in cfg.APL.items():
                msg += f"Applicant {Applicant} is {'still working on their application' if aplication['open'] else 'waiting for admin approval'}.\n"
            if len(cfg.APL) > 0:
                msg += f"You can view a specific application by entering `{cfg.PREFIX}showapp <applicant>`."
            await ctx.channel.send(msg)
            return

    @command(name='cancelapp', help="Displays the given Applicants application if it has been submitted. When Applicant is omitted, shows all applications.")
    @has_role(cfg.ADMIN_ROLE)
    async def cancelapp(self, ctx, Applicant, *Message):
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        if not Applicant in cfg.APL:
            await ctx.channel.send(f"Applicant {Applicant} couldn't be found.")
            return
        del cfg.APL[Applicant]
        if Message:
            Message = " ".join(Message)
        await ctx.channel.send(f"Application for {Applicant} has been cancelled.")
        await Applicant.dm_channel.send(f"Your application was cancelled by an administrator.{' Message: ' + Message + '.' if len(Message) > 0 else ''}")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been cancelled.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been cancelled.")

    @command(name='reloadsheets', help="Updates all default messages and questions from google sheets.")
    @has_role(cfg.ADMIN_ROLE)
    async def reloadsheets(self, ctx):
        update_questions()
        await ctx.channel.send("Default messages and questions have been reloaded from google sheets.")
        logger.info("Default messages and questions have been reloaded from google sheets.")

class RCon(commands.Cog, name="RCon commands"):
    @command(name='listplayers', help="Shows a list of all players online right now")
    async def listplayers(self, ctx):
        try:
            playerlist = rcon.execute((cfg.RCON_IP, cfg.RCON_PORT), cfg.RCON_PASSWORD, "ListPlayers")
        except Exception as error:
            print("excetion raised", type(error), error.args[1])
            raise exc.RConConnectionError(error.args[1])
        print("playerlist:", playerlist)
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

    @command(name='whitelist', help="Whitelists the player with the given discord nick and SteamID64")
    @has_role(cfg.ADMIN_ROLE)
    async def whitelist(self, ctx, Player: Member, SteamID64: int):
        result = await whitelist_player(ctx, SteamID64, Player)
        if result == "NotSteamIdError":
            raise exc.NotSteamIdError()
        elif result == "IsGabesIDError":
            raise exc.IsGabesIDError()
        elif result.find("FailedError") >= 0:
            raise commands.BadArgument(result[12:])
        else:
            await ctx.send(result)
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            logger.info(f"ERROR: Author: {ctx.author} / Command: {ctx.message.content}. {result}")

class General(commands.Cog, name="General commands"):
    @command(name='roll', help="Rolls a dice in NdN format")
    async def roll(self, ctx, *, Dice: str):
        result = await roll_dice(Dice)
        await ctx.send(f"{ctx.author.mention} rolled: " + result)

    @command(name="setsteamid", help="Set your 17 digit SteamID64 (the one used to whitelist you)")
    @has_not_role(cfg.NOT_APPLIED_ROLE)
    async def setsteamid(self, ctx, SteamID64: str):
        if not SteamID64.isnumeric() or len(SteamID64) != 17:
            raise exc.NotSteamIdError()
        elif SteamID64 == "76561197960287930":
            raise exc.IsGabesIDError()
        sessionUser.query(User).filter(or_(User.SteamID64==SteamID64, User.disc_user==str(ctx.author))).delete()
        sessionUser.add(User(SteamID64=SteamID64, disc_user=str(ctx.author)))
        sessionUser.commit()
        logger.info(f"Player {ctx.author} set their SteamID64 to {SteamID64}.")
        await ctx.channel.send(f"Your SteamID64 has been set to {SteamID64}.")

    @command(name="getsteamid", help="Checks if your SteamID64 has been set.")
    @has_not_role(cfg.NOT_APPLIED_ROLE)
    async def getsteamid(self, ctx):
        disc_user = await commands.MemberConverter().convert(ctx, ctx.author.mention)
        SteamID64 = get_steamID64(disc_user)
        if SteamID64:
            await ctx.channel.send(f"Your SteamID64 is currently set to {SteamID64}.")
        else:
            await ctx.channel.send(f"Your SteamID64 has not been set yet. You can set it with `{cfg.PREFIX}setsteamid <SteamID64>`")

    @command(name="whois", help="Tells you the chararacter name(s) belonging to the given discord user or vice versa")
    @has_role_greater_or_equal(cfg.SUPPORT_ROLE)
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

bot.add_cog(Applications())
bot.add_cog(RCon())
bot.add_cog(General())
bot.run(cfg.DISCORD_TOKEN)
