# TERPBot v1.2.1
import os, random, discord, asyncio, config as saved
from datetime import datetime, timedelta
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
from cogs.general import General
from cogs.rcon import RCon
from cogs.magic import Mag

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(PREFIX, intents=intents, case_insensitive=True)

async def next_time(d, t):
    weekdays = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    now = datetime.utcnow().replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=t.microsecond)
    days_ahead = (weekdays[d] - now.weekday()) % 7
    if days_ahead == 0 and datetime.utcnow().time() > t:
        days_ahead = 7
    return now + timedelta(days=days_ahead)

async def magic_rolls():
    while True:
        # schedule the next function call
        then = await next_time(UPDATE_MAGIC_DAY, UPDATE_MAGIC_TIME)
        await discord.utils.sleep_until(then)
        # perform the actual magic rolls
        mchars = session.query(MagicChars).filter_by(active=True).all()
        if len(mchars) == 0:
            await saved.CHANNEL[MAGIC_ROLLS].send("No magic chars registered.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. No magic chars registered.")
            continue
        longest_name = session.query(func.max(func.length(MagicChars.name))).filter_by(active=True).scalar()
        hd = ["Character", " MP"]
        wd = longest_name if longest_name > len(hd[0]) else len(hd[0])
        await saved.CHANNEL[MAGIC_ROLLS].send(f"Mana point rolls for calendar week **{datetime.utcnow().isocalendar()[1]}**:")
        output = f"```{hd[0]:<{wd}} | {hd[1]:>{len(hd[1])}}"
        output += '\n' + '-' * (len(output) - 3)
        for mchar in mchars:
            mchar.mana = random.randint(MAGIC_ROLL_RANGE[0], MAGIC_ROLL_RANGE[1])
            chunk = f"\n{mchar.name:<{wd}} | {mchar.mana:>{len(hd[1])}}"
            # ensure that the whole output isn't longer than 2000 characters
            if (len(output) + len(chunk)) >= 2000:
                await saved.CHANNEL[MAGIC_ROLLS].send(output)
                output = chunk
            else:
                output += chunk
        session.commit()
        await saved.CHANNEL[MAGIC_ROLLS].send(output + "```")

async def update_roles():
    while True:
        # schedule the next function call
        now = datetime.utcnow()
        date = now.date()
        if now.time() > UPDATE_ROLES_TIME:
            date = now.date() + timedelta(days=1)
        then = datetime.combine(date, UPDATE_ROLES_TIME)
        await discord.utils.sleep_until(then)
        # perfom the actual role update
        roles = {}
        for role in saved.GUILD.roles:
            roles[role.name] = role

        # clan roles that are required based on the actual Characters table
        logger.info("Starting to reindex discord clan roles.")

        guild_members = {}
        for member in saved.GUILD.members:
            guild_members[str(member.id)] = member

        required_clan_roles = {}
        for char in session.query(Characters):
            if char.has_guild:
                guild_name = char.guild.name
                if guild_name in CLAN_IGNORE_LIST:
                    continue
                user = char.user
                if not user:
                    logger.info(f"Couldn't find User for char {char.name} for clan roles indexing")
                    continue
                disc_id = user.disc_id
                if not disc_id:
                    logger.info(f"Couldn't find DiscordID for char {char.name} for clan roles indexing")
                    continue
                if not disc_id in guild_members:
                    logger.info(f"Couldn't get member by DiscordID for {char.name} for clan roles indexing")
                    continue
                member = guild_members[disc_id]
                if not guild_name in required_clan_roles:
                    required_clan_roles[guild_name] = [member]
                else:
                    required_clan_roles[guild_name].append(member)

        # index roles by position
        roles_by_pos = {}
        for name, role in roles.items():
            roles_by_pos[role.position] = role

        roles_idx = []
        for pos in sorted(roles_by_pos):
            name = roles_by_pos[pos].name
            if name == CLAN_START_ROLE:
                start_pos = len(roles_idx)
            elif name == CLAN_END_ROLE:
                end_pos = len(roles_idx)
            roles_idx.append(name)

        before_clan_roles = roles_idx[:end_pos+1]
        after_clan_roles = roles_idx[start_pos:]

        # create a slice of only those guilds that are actually required
        clan_roles = []
        for name in sorted(roles_idx[end_pos+1:start_pos]):
            # remove existing roles that are no longer required
            if not name in required_clan_roles:
                await roles[name].delete()
                del roles[name]
            # create the slice of existing clans otherwise
            else:
                clan_roles.append(name)

        # add roles and update their members as required
        for name, members in required_clan_roles.items():
            # add clan roles not existing yet
            if not name in roles:
                clan_roles.append(name)
                hoist = CLAN_ROLE_HOIST
                mentionable = CLAN_ROLE_MENTIONABLE
                roles[name] = await saved.GUILD.create_role(name=name, hoist=hoist, mentionable=mentionable)
                # add all members to that role
                for member in members:
                    await member.add_roles(roles[name])
            # update existing roles
            else:
                # add members not alread assigned to the role
                for member in members:
                    if not member in roles[name].members:
                        await member.add_roles(roles[name])
                # remove members that are assigned to the role but shouldn't be
                for member in roles[name].members:
                    if not member in members:
                        await member.remove_roles(roles[name])

        # create a positions list for the roles
        reindexed_roles = before_clan_roles + sorted(clan_roles, reverse=True) + after_clan_roles
        positions = {}
        for position in range(1, len(reindexed_roles)):
            name = reindexed_roles[position]
            positions[roles[name]] = position

        # reorder the clan roles alphabetically
        await saved.GUILD.edit_role_positions(positions)
        logger.info("Finished reindexing discord clan roles.")

# errors in tasks raise silently normally so lets make them speak up
def exception_catching_callback(task):
    if task.exception():
        logger.error("Error in task.")
        task.print_stack()

##############
''' Events '''
##############

@bot.event
async def on_ready():
    rcon.RCONMessage.ENCODING = "utf-8"
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
    if UPDATE_ROLES_TIME:
        update_roles_task = asyncio.create_task(update_roles())
        update_roles_task.add_done_callback(exception_catching_callback)
    if ROLL_FOR_MANA:
        magic_roles_task = asyncio.create_task(magic_rolls())
        magic_roles_task.add_done_callback(exception_catching_callback)

@bot.event
async def on_member_join(member):
    logger.info(f"{member} just joined the discord.")
    await member.add_roles(saved.ROLE[NOT_APPLIED_ROLE])
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
    logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {str(error)}")

@bot.command(hidden=True)
@has_role(ADMIN_ROLE)
async def reload(ctx, extension):
    bot.reload_extension(f"cogs.{extension}")
    await ctx.send(f"Cog {extension} has been reloaded.")

bot.run(DISCORD_TOKEN)
