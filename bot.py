# bot.py
import os
import random
import discord
from discord import ChannelType
from discord.ext import commands
from valve import rcon
import config as cfg
from logger import logger
from checks import has_role
from helpers import *

bot = commands.Bot(cfg.PREFIX)

##############
''' Events '''
##############

@bot.event
async def on_ready():
    rcon.RCONMessage.ENCODING = "utf-8"
    print(f"{bot.user.name} has connected to Discord.")
    logger.info(f"{bot.user.name} has connected to Discord.")
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
    # load cogs
    for filename in os.listdir("cogs"):
        if filename.endswith(".py"):
            bot.load_extension(f"cogs.{filename[:-3]}")

@bot.event
async def on_member_join(member):
    logger.info(f"{member} just joined the discord.")
    await member.edit(roles=member.roles + [cfg.ROLE[cfg.NOT_APPLIED_ROLE]])
    await cfg.CHANNEL[cfg.WELCOME].send(parse(member, cfg.GREETING))

@bot.event
async def on_member_remove(member):
    application = await get_application(member)
    if application and not application.status in ['rejeted' or 'approved']:
        await delete_application(application)
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{member} just left discord. Ongoing application was cancelled")
        logger.info(f"{member} just left discord. Ongoing application was cancelled")
    else:
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{member} just left discord.")
        logger.info(f"{member} just left discord.")

@bot.event
async def on_message(message):
    application = await get_application(message.author)
    if not message.channel.type == ChannelType.private or not application:
        await bot.process_commands(message)
        return
    if message.content[0] == cfg.PREFIX:
        word = message.content.split(None, 1)[0][1:]
        for cmd in bot.commands:
            if cmd.name == word:
                await bot.process_commands(message)
                return
    if not application or not await can_edit_questions(application):
        await message.author.dm_channel.send(parse(message.author, cfg.APP_CLOSED))
        return
    if application.current_question < 0:
        return
    questions = await get_questions(application)
    questions[application.current_question - 1].answer = message.content
    sessionSupp.commit()
    questionId = await get_next_unanswered(application)
    if questionId > 0:
        await send_question(message.author, questionId)
    elif not application.status == 'finished':
        application.status = 'finished'
        await message.author.dm_channel.send(parse(message.author, cfg.FINISHED))
    application.current_question = questionId
    sessionSupp.commit()

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

@bot.command(hidden=True)
@has_role(cfg.ADMIN_ROLE)
async def reload(ctx, extension):
    bot.reload_extension(f"cogs.{extension}")
    await ctx.send(f"Cog {extension} has been reloaded.")

bot.run(cfg.DISCORD_TOKEN)
