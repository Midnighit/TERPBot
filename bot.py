# bot.py
import os
import re
import random
import config
import logging
from logging.handlers import RotatingFileHandler
from asyncio import wait_for, TimeoutError
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from discord import DiscordException, ChannelType, Member, Guild
from discord.ext import commands
from discord.ext.commands import command, check
from mcrcon import MCRcon
from google_api import sheets

bot = commands.Bot(config.PREFIX)
logger = logging.getLogger(__name__)
engine = create_engine('sqlite:///users.db')
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()
Base.metadata.create_all(engine)

################
''' SQlite '''
################

# setup the classes
engine = create_engine('sqlite:///users.db')
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    SteamID64 = Column(String(17), unique=True, nullable=False)
    disc_user = Column(String, unique=True, nullable=False)

    def __repr__(self):
        return f"<User(SteamID64='{self.SteamID64}', disc_user='{self.disc_user}')>"

# create the table
Base.metadata.create_all(engine)

# instantiate a session object
session = Session()

########################
''' Helper functions '''
########################

async def send_question(author, id, msg=''):
    await author.dm_channel.send(f"{msg}\n__**Question {id + 1}:**__\n> {parse(author, config.QUESTIONS[id])}")

async def send_overview(author, msg='', submitted=False):
    channel = config.CHANNEL[config.APPLICATIONS] if submitted else author.dm_channel
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

async def whitelist_player(SteamID64):
    if len(str(SteamID64)) != 17:
        return {'msg': "SteamID64 must be a 17 digits number", 'success': False}
    with MCRcon(config.RCON_IP, config.ADMIN_PASSWORD, port=config.RCON_PORT) as mcr:
        msg =  mcr.command(f"WhitelistPlayer {SteamID64}")
        success = False if msg.find("Invalid argument") >= 0 else True
        return {'msg': msg, 'success': success}

def update_questions():
    config.QUESTIONS = [value[0] for value in sheets.read(config.SPREADSHEET_ID, config.QUESTIONS_RANGE)]
    config.GREETING = sheets.read(config.SPREADSHEET_ID, config.GREETING_RANGE)[0][0]
    config.APPLIED = sheets.read(config.SPREADSHEET_ID, config.APPLIED_RANGE)[0][0]
    config.FINISHED =sheets.read(config.SPREADSHEET_ID, config.FINISHED_RANGE)[0][0]
    config.COMMITED = sheets.read(config.SPREADSHEET_ID, config.COMMITED_RANGE)[0][0]
    config.ACCEPTED = sheets.read(config.SPREADSHEET_ID, config.ACCEPTED_RANGE)[0][0]
    config.REJECTED = sheets.read(config.SPREADSHEET_ID, config.REJECTED_RANGE)[0][0]
    config.WHITELISTING_FAILED = sheets.read(config.SPREADSHEET_ID, config.WHITELISTING_FAILED_RANGE)[0][0]
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

def get_steam64Id(author):
    result = re.search(r'(7\d{16})', config.APL[author]['answers'][config.STEAMID_QUESTION])
    result = result.group(1) if result else None
    return result

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
    print(f"{bot.user.name} has connected to Discord!")
    logger.info(f"{bot.user.name} has connected to Discord!")
    # determine discord server
    for guild in bot.guilds:
        if guild.name == config.DISCORD_NAME:
            config.GUILD = guild
            print(f"Discord server {guild.name} was found (id = {guild.id})")
            break
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
    print("Questions have been read from the spreadsheet")
    # initialize randomizer
    random.seed()
    print("Seed for RNG generated")

@bot.event
async def on_member_join(member):
    await config.CHANNEL[config.WELCOME].send(parse(member, config.GREETINGS))

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
            {'timestamp': datetime.utcnow(), 'open': True, 'questionId': 0, 'answers': {}}

    @apply.error
    async def applicant_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            if config.APL[ctx.author]['finished']:
                msg = f"You already have an open application and all questions have been answered. You can review them with `{config.PREFIX}overview` and use `{config.PREFIX}submit` to finish the application and send it to the admins."
                await ctx.author.dm_channel.send(msg)
            else:
                msg = f"You already have an open application. Answer questions with `{config.PREFIX}a <answer text>`."
                await send_question(ctx.author, config.APL[ctx.author]['questionId'], msg=msg)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Question number must be between 1 and {len(config.QUESTIONS)}")
        else:
            await ctx.send(error)
            logger.error(error)

    @command(name='a', help="Used to answer questions during the application process")
    @check(is_applicant)
    @check(is_private)
    async def a(self, ctx, *, answer: str):
        if not config.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, config.APP_CLOSED))
            return
        config.APL[ctx.author]['answers'][config.APL[ctx.author]['questionId']] = answer
        questionId = find_next_unanswered(ctx.author)
        if questionId >= 0:
            await send_question(ctx.author, questionId)
            config.APL[ctx.author]['questionId'] = questionId
        else:
            await ctx.author.dm_channel.send(parse(ctx.author, config.FINISHED))

    @command(name='q', help='Used to switch to a given question')
    @check(is_applicant)
    @check(is_private)
    async def q(self, ctx, *questionId: int):
        if not config.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, config.APP_CLOSED))
            return
        if not questionId:
            await send_question(ctx.author, config.APL[ctx.author]['questionId'])
            return
        if questionId[0] < 1 or questionId[0] > len(config.QUESTIONS):
            raise commands.BadArgument
        await send_question(ctx.author, questionId[0] - 1)
        config.APL[ctx.author]['questionId'] = questionId[0] - 1

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
        msg = f"{ctx.author} has filled out the application. You can now either \n`{config.PREFIX}accept <applicant> <message>` or `{config.PREFIX}reject <applicant> <message>` it.\nIf <message> is omitted a default message will be sent."
        await send_overview(ctx.author, msg=msg, submitted=True)

    @command(name='cancel', help="Cancel your application")
    @check(is_applicant)
    async def cancel(self, ctx):
        await config.CHANNEL[config.APPLICATIONS].send(f"{ctx.author} has canceled their application.")
        await ctx.author.dm_channel.send("Your application has been canceled.")
        print(f"{ctx.author} has canceled their application.")
        del config.APL[ctx.author]

    @a.error
    @q.error
    @overview.error
    @submit.error
    @cancel.error
    async def application_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f"You do not have an open application. Start one with `{config.PREFIX}apply`.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Question number must be between 1 and {len(config.QUESTIONS)}")
        else:
            await ctx.send(error)
            logger.error(error)

    @command(name='accept', help="Accept the application. If message is ommitted a default message will be sent")
    @commands.has_role(config.ADMIN_ROLE)
    async def accept(self, ctx, applicant: Member, *message):
        # remove Not Applied role
        if message:
            message = " ".join(message)
        roles = []
        for role in applicant.roles:
            if role.name != config.NOT_APPLIED_ROLE:
                roles.append(role)
        await applicant.edit(roles=roles)
        # Whitelist applicant
        SteamID64 = get_steam64Id(applicant)
        if SteamID64:
            try:
                print(f"[{datetime.utcnow()}] Trying to whitelist...")
                result = await wait_for(whitelist_player(SteamID64), timeout=5)
                print(f"[{datetime.utcnow()}] Whitelisting successful.")
            except TimeoutError:
                print(f"[{datetime.utcnow()}] Whitelisting timed out.")
                result = {'msg': "Whitelisting attempt timed out", 'success': False}
        else:
            result = {'msg': "No SteamID64 was given.", 'success': False}
        await config.CHANNEL[config.APPLICATIONS].send(result['msg'])
        # Store SteamID64 <-> Discord Name link in db
        if result['success']:
            session.add(User(SteamID64=SteamID64, disc_user=str(applicant)))
            session.commit()
        # Send feedback to applications channel and to applicant
        await config.CHANNEL[config.APPLICATIONS].send(f"{applicant}'s application has been accepted.")
        if not message:
            message = parse(ctx.author, config.ACCEPTED)
        if result['success']:
            await applicant.dm_channel.send(message + "\n" + parse(ctx.author, config.WHITELISTING_SUCCEEDED))
        else:
            await applicant.dm_channel.send(message + "\n" + parse(ctx.author, config.WHITELISTING_FAILED))
        # remove application from list of open applications
        del config.APL[applicant]
        print(f"{ctx.author} has accepted {applicant}'s application.")

    @command(name='reject', help="Reject the application. If message is omitted a default message will be sent")
    @commands.has_role(config.ADMIN_ROLE)
    async def reject(self, ctx, applicant: Member, *message):
        # Send feedback to applications channel and to applicant
        await config.CHANNEL[config.APPLICATIONS].send(f"{applicant}'s application has been rejected.")
        if not message:
            await applicant.dm_channel.send(parse(ctx.author, config.REJECTED))
        else:
            await applicant.dm_channel.send(" ".join(message))
        # remove application from list of open applications
        del config.APL[applicant]
        print(f"{ctx.author} has rejected {applicant}'s application.")

    @accept.error
    @reject.error
    async def accept_reject_error(self, ctx, error):
        print(f"accept_reject_error: {error}")
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to accept or reject applications")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Applicant couldn't be found")
        else:
            await ctx.send(error)
            logger.error(error)

class RCon(commands.Cog, name="RCon commands"):
    @command(name='listplayers', help="Shows a list of all players online right now")
    async def listplayers(self, ctx):
        with MCRcon(config.RCON_IP, config.ADMIN_PASSWORD, port=config.RCON_PORT) as mcr:
            playerlist = mcr.command("ListPlayers")
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
            await ctx.send(f"{len(names)} players online:\n" + ', '.join(names))

    @listplayers.error
    async def listplayers_error(self, ctx, error):
        await ctx.send(error)
        logger.error(error)

    @command(name='whitelist', help="Whitelists the player with the given SteamID64")
    @commands.has_role(config.ADMIN_ROLE)
    async def whitelist(self, ctx, SteamID64: int):
        try:
            result = await wait_for(whitelist_player(SteamID64), timeout=5)
        except TimeoutError:
            result = {'msg': "Whitelisting attempt timed out", 'success': False}
        await ctx.send(result['msg'])

    @whitelist.error
    async def whitelist_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("SteamID64 must be a 17 digits number")
        else:
            await ctx.send(error)
            logger.error(error)

class General(commands.Cog, name="General commands"):
    @command(name='roll', help="Rolls a dice in NdN format")
    async def roll(self, ctx, dice: str):
        try:
            rolls, limit = map(int, dice.split('d'))
        except Exception:
            await ctx.send('Format has to be in NdN!')
            return
        l = [random.randint(1, limit) for r in range(rolls)]
        s = ', '.join([str(r) for r in l])
        result = f"{s} (total: {sum(l)})" if len(l) > 1 else s
        await ctx.send(result)

    @roll.error
    async def roll_error(self, ctx, error):
        await ctx.send(error)
        logger.error(error)

bot.add_cog(Applications())
bot.add_cog(RCon())
bot.add_cog(General())
bot.run(config.DISCORD_TOKEN)
