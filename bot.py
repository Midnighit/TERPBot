# TERPBot v1.2.0
import os, random, discord, config as saved
from threading import Timer
from discord import ChannelType
from discord.ext import commands
from valve import rcon
from logger import logger
from checks import has_role
from config import *
from exiles_api import *
from cogs.applications import Applications as Apps
from cogs.applications import General
from cogs.applications import RCon

bot = commands.Bot(PREFIX)

##############
''' Events '''
##############

@bot.event
async def on_ready():
    rcon.RCONMessage.ENCODING = "utf-8"
    print(f"{bot.user.name} has connected to Discord.")
    logger.info(f"{bot.user.name} has connected to Discord.")
    # determine discord server
    saved.GUILD = discord.utils.get(bot.guilds, name=DISCORD_NAME)
    if saved.GUILD:
        print(f"Discord server {saved.GUILD.name} ({saved.GUILD.id}) was found.")
    else:
        exit(f"{DISCORD_NAME} wasn't found. Please check cfg.py or authorize the bot.")
    # get all categories
    for category in saved.GUILD.categories:
        saved.CATEGORY[category.name] = category
    # get all channels
    for channel in saved.GUILD.channels:
        saved.CHANNEL[channel.name] = channel
    # get all roles
    for role in saved.GUILD.roles:
        saved.ROLE[role.name] = role
    # create channel and category if necessary
    for channel in saved.DISCORD_CHANNELS:
        if not channel[0] in saved.CHANNEL:
            if channel[1] and not channel[1] in saved.CATEGORY:
                saved.CATEGORY[channel[1]] = await saved.GUILD.create_category(channel[1])
            category = saved.CATEGORY[channel[1]] if channel[1] else None
            saved.CHANNEL[channel[0]] = await saved.GUILD.create_text_channel(channel[0], category=category)
            print(f"{channel[0]} channel was created (id = {saved.CHANNEL[channel[0]].id})")
    # initialize randomizer
    random.seed()
    # load cogs
    for filename in os.listdir("cogs"):
        if filename.endswith(".py"):
            bot.load_extension(f"cogs.{filename[:-3]}")

@bot.event
async def on_member_join(member):
    logger.info(f"{member} just joined the discord.")
    await member.edit(roles=[saved.ROLE[NOT_APPLIED_ROLE]])
    await saved.CHANNEL[WELCOME].send(Apps.parse(member, TextBlocks.get('GREETING')))

@bot.event
async def on_member_remove(member):
    app = session.query(Applications).filter_by(disc_id=member.id).first()
    if app and not app.status in ('rejected', 'approved'):
        session.delete(app)
        session.commit()
        logger.info(f"{member} just left discord. Ongoing application was cancelled")
    else:
        logger.info(f"{member} just left discord.")

@bot.event
async def on_message(message):
    if message.channel == saved.CHANNEL[STATUS]:
        if message.content.startswith(SHUTDOWN_MSG):
            logger.info("Reading time from game server...")
            try:
                time = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, "TERPO getTimeDecimal")
                logger.info(f"Time read successfully: {time}")
            except Exception as error:
                raise RConConnectionError(error.args[1])
            saved.LAST_RESTART_TIME = time
        elif message.content.startswith(RESTART_MSG):
            delayed_set_time = Timer(150.0, RCon.set_time_decimal)
            delayed_set_time.start()
    app = session.query(Applications).filter_by(disc_id=message.author.id).first()
    if not message.channel.type == ChannelType.private or not app:
        if message.content in IGNORE_CMDS:
            return
        await bot.process_commands(message)
        return
    if message.content[0] == PREFIX:
        word = message.content.split(None, 1)[0][1:]
        for cmd in bot.commands:
            if cmd.name == word:
                await bot.process_commands(message)
                return
    if app and app.status in ('rejected', 'accepted'):
        return
    if not app or not app.can_edit_questions():
        await message.author.dm_channel.send(Apps.parse(message.author, TextBlocks.get('APP_CLOSED')))
        return
    if app.current_question < 0:
        return
    questions = app.questions
    questions[app.current_question-1].answer = message.content
    session.commit()
    app.current_question = app.first_unanswered
    if app.current_question > 0:
        question = Apps.get_question_msg(questions, message.author, app.current_question)
        await message.author.dm_channel.send(question)
    elif not app.status == 'finished':
        app.status = 'finished'
        await message.author.dm_channel.send(Apps.parse(message.author, TextBlocks.get('FINISHED')))
    session.commit()

@bot.event
async def on_command_error(ctx, error):
    if saved.C_ERR:
        saved.C_ERR = False
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

@bot.command(hidden=True)
@has_role(ADMIN_ROLE)
async def reload(ctx, extension):
    bot.reload_extension(f"cogs.{extension}")
    await ctx.send(f"Cog {extension} has been reloaded.")

bot.run(DISCORD_TOKEN)
