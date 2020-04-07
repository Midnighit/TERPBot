# bot.py
import os
import re
import random
import config
from asyncio import wait_for, TimeoutError
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from discord import DiscordException, ChannelType, Member
from discord.ext import commands
from discord.ext.commands import command, check
from mcrcon import MCRcon
from google_api import sheets

bot = commands.Bot(config.PREFIX)
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
    await author.dm_channel.send(f"{msg}\n__**Question {id + 1}:**__\n> {config.QUESTIONS[id]}")

async def send_overview(author, msg='', commited=False):
    channel = config.APL_CHAN if commited else author.dm_channel
    buffer = msg + "\n" if msg else ''
    for id in range(len(config.QUESTIONS)):
        if id in config.APL[author]['answers']:
            if len(buffer) + 21 + len(config.QUESTIONS[id]) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += f"__**Question {id + 1}:**__\n> {config.QUESTIONS[id]}\n"
            if len(buffer) + len(config.APL[author]['answers'][id]) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += config.APL[author]['answers'][id] + "\n"
    await channel.send(buffer)

async def whitelist_player(SteamID64):
    if len(str(SteamID64)) != 17:
        return {'msg': "SteamID64 must be a 17 digits number", 'success': False}
    with MCRcon(config.RCON_IP, config.ADMIN_PASSWORD, port=config.RCON_PORT) as mcr:
        msg =  mcr.command(f"WhitelistPlayer {SteamID64}")
        success = False if msg.find("Invalid argument") >= 0 else True
        return {'msg': msg, 'success': success}

def update_questions():
    config.QUESTIONS = [parse(value[0]) for value in sheets.read(config.SPREADSHEET_ID, config.QUESTIONS_RANGE)]
    config.GREETINGS = parse(sheets.read(config.SPREADSHEET_ID, config.GREETING_RANGE)[0][0])
    config.FINISHED = parse(sheets.read(config.SPREADSHEET_ID, config.FINISHED_RANGE)[0][0])
    config.COMMITED = parse(sheets.read(config.SPREADSHEET_ID, config.COMMITED_RANGE)[0][0])
    config.ACCEPTED = parse(sheets.read(config.SPREADSHEET_ID, config.ACCEPTED_RANGE)[0][0])
    config.REJECTED = parse(sheets.read(config.SPREADSHEET_ID, config.REJECTED_RANGE)[0][0])
    config.WHITELISTING_FAILED = parse(sheets.read(config.SPREADSHEET_ID, config.WHITELISTING_FAILED_RANGE)[0][0])
    config.WHITELISTING_SUCCEEDED = parse(sheets.read(config.SPREADSHEET_ID, config.WHITELISTING_SUCCEEDED_RANGE)[0][0])
    config.APP_CLOSED = parse(sheets.read(config.SPREADSHEET_ID, config.APP_CLOSED_RANGE)[0][0])

def find_next_unanswered(author):
    if len(config.APL[author]['answers']) >= len(config.QUESTIONS):
        return -1
    for id in range(len(config.QUESTIONS)):
        if id not in config.APL[author]['answers']:
            return id
    return -1

def parse(msg):
    return msg.replace('{PREFIX}', config.PREFIX)

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

async def is_admin(ctx):
    if not hasattr(ctx.author, 'roles'):
        return False
    for role in ctx.author.roles:
        if role.name == config.ADMIN_ROLE:
            return True
    return False

async def is_not_bot(ctx):
    return ctx.author != bot.user

##############
''' Events '''
##############

@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    for channel in bot.get_all_channels():
        if channel.name == 'applications':
            config.APL_CHAN = channel
            print(f"Applications channel was found (id = {channel.id})")
    if not config.APL_CHAN:
        config.APL_CHAN = await bot.guild.create_text_channel('applications')
        print(f"Applications channel was created (id = {config.APL_CHAN.id})")
    update_questions()
    print("Questions have been read from the spreadsheet")
    random.seed()
    print("Seed for RNG generated")

@bot.event
async def on_member_join(member):
    await member.create_dm()
    await member.dm_channel.send(f"Hi {member.display_name}, welcome to the discord server of The Exiled RP!")

####################
''' Bot commands '''
####################

class Applications(commands.Cog, name="Application commands"):
    @command(name='apply', help="Starts the application process")
    @check(is_not_applicant)
    async def apply(self, ctx):
        await ctx.author.create_dm()
        await send_question(ctx.author, 0, msg=config.GREETINGS)
        config.APL[ctx.author] = \
            {'timestamp': datetime.utcnow(), 'open': True, 'questionId': 0, 'finished': False, 'answers': {}}

    @apply.error
    async def applicant_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            if config.APL[ctx.author]['finished']:
                msg = f"You already have an open application and all questions have been answered. You can review them with `{config.PREFIX}overview` and use `{config.PREFIX}commit` to finish the application and send it to the admins."
                await ctx.author.dm_channel.send(msg)
            else:
                msg = f"You already have an open application. Answer questions with `{config.PREFIX}a <answer text>`."
                await send_question(ctx.author, config.APL[ctx.author]['questionId'], msg=msg)

        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Question number must be between 1 and {len(config.QUESTIONS)}")

    @command(name='a', help="Used to answer questions during the application process")
    @check(is_applicant)
    @check(is_private)
    async def a(self, ctx, *, answer: str):
        if not config.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(config.APP_CLOSED)
            return
        config.APL[ctx.author]['answers'][config.APL[ctx.author]['questionId']] = answer
        questionId = find_next_unanswered(ctx.author)
        if questionId >= 0:
            await send_question(ctx.author, questionId)
            config.APL[ctx.author]['questionId'] = questionId
        elif not config.APL[ctx.author]['finished']:
            config.APL[ctx.author]['finished'] = True
            await ctx.author.dm_channel.send(config.FINISHED)

    @command(name='q', help='Used to switch to a given question')
    @check(is_applicant)
    @check(is_private)
    async def q(self, ctx, questionId: int):
        if not config.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(config.APP_CLOSED)
            return
        if questionId < 1 or questionId > len(config.QUESTIONS):
            raise commands.BadArgument
        questionId -= 1
        await send_question(ctx.author, questionId)
        config.APL[ctx.author]['questionId'] = questionId

    @command(name='overview', help="Display all questions that have already been answered")
    @check(is_applicant)
    async def overview(self, ctx):
        await send_overview(ctx.author)

    @command(name='commit', help="Commit your application and send it to the admins")
    @check(is_applicant)
    async def commit(self, ctx):
        if len(config.QUESTIONS) > len(config.APL[ctx.author]['answers']):
            await ctx.author.dm_channel.send("Please answer all questions first.")
            return
        if not config.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(config.APP_CLOSED)
            return
        config.APL[ctx.author]['open'] = False
        await ctx.author.dm_channel.send(config.COMMITED)
        msg = f"{ctx.author.mention} has filled out the following application. You can now either `{config.PREFIX}accept <applicant> <message>` or `{config.PREFIX}reject <applicant> <message>` it. If <message> is omitted a default message will be sent."
        await send_overview(ctx.author, msg=msg, commited=True)

    @a.error
    @q.error
    @overview.error
    @commit.error
    async def not_applicant_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(f"You do not have an open application. Start one with `{config.PREFIX}apply`.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Question number must be between 1 and {len(config.QUESTIONS)}")

    @command(name='accept', help="Accept the application. If message is ommitted a default message will be sent")
    @check(is_admin)
    async def accept(self, ctx, applicant: Member, *, message):
        # remove Not Applied role
        role_to_remove = None
        for role in applicant.roles:
            if role.name == "Not Applied":
                role_to_remove = role
                break
        if role_to_remove:
            applicant.roles.remove(role_to_remove)
        await applicant.edit(roles=applicant.roles)
        # Whitelist applicant
        SteamID64 = get_steam64Id(applicant)
        if SteamID64:
            try:
                result = await wait_for(whitelist_player(SteamID64), timeout=5)
            except TimeoutError:
                result = {'msg': "Whitelisting attempt timed out", 'success': False}
        else:
            result = {'msg': "No SteamID64 was given.", 'success': False}
        await config.APL_CHAN.send(result['msg'])
        # Store SteamID64 <-> Discord Name link in db
        if result['success']:
            session.add(User(SteamID64=SteamID64, disc_user=str(applicant)))
            session.commit()
        # Send feedback to applications channel and to applicant
        await config.APL_CHAN.send(f"{applicant.mention}'s application has been accepted.")
        if not message:
            message = config.ACCEPTED
        if result['success']:
            await applicant.dm_channel.send(message + "\n" + config.WHITELISTING_SUCCEEDED)
        else:
            await applicant.dm_channel.send(message + "\n" + config.WHITELISTING_FAILED)
        # remove application from list of open applications
        del config.APL[applicant]

    @command(name='reject', help="Reject the application. If message is omitted a default message will be sent")
    @check(is_admin)
    async def reject(self, ctx, applicant: Member, *, message):
        # Send feedback to applications channel and to applicant
        await config.APL_CHAN.send(f"{applicant.mention}'s application has been rejected.")
        if not message:
            await applicant.dm_channel.send(config.REJECTED)
        else:
            await applicant.dm_channel.send(message)
        # remove application from list of open applications
        del config.APL[applicant]

    @accept.error
    @reject.error
    async def accept_reject_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required permissions to accept or reject applications")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Applicant couldn't be found")

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

    @command(name='whitelist', help="Whitelists the player with the given SteamID64")
    @check(is_admin)
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

bot.add_cog(Applications())
bot.add_cog(RCon())
bot.add_cog(General())
bot.run(config.DISCORD_TOKEN)
