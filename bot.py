# TERPBot v1.2.1
import os, random, discord, asyncio
from datetime import datetime, timedelta
from discord import ChannelType
from discord.ext import commands
from logger import logger
from checks import has_role, init_checks
from config import *
from exiles_api import *
from functions import *
from cogs.applications import Applications as Apps

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(PREFIX, intents=intents, case_insensitive=True)

async def magic_rolls():
    channels = get_channels(bot=bot)
    weekdays = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    while True:
        # schedule the next function call
        now = datetime.utcnow()
        today = datetime.combine(now, UPDATE_MAGIC_TIME)
        days_ahead = (weekdays[UPDATE_MAGIC_DAY] - today.weekday()) % 7
        if days_ahead == 0 and now.time() > UPDATE_MAGIC_TIME:
            days_ahead = 7
        then = today + timedelta(days=days_ahead)
        await discord.utils.sleep_until(then)
        # perform the actual magic rolls
        mchars = session.query(MagicChars).filter_by(active=True).order_by(MagicChars.name).all()
        if len(mchars) == 0:
            await channels[MAGIC_ROLLS].send("No magic chars registered.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. No magic chars registered.")
            continue
        longest_name = session.query(func.max(func.length(MagicChars.name))).filter_by(active=True).scalar()
        hd = ["Character", " MP"]
        wd = longest_name if longest_name > len(hd[0]) else len(hd[0])
        await channels[MAGIC_ROLLS].send(f"Mana point rolls for calendar week **{datetime.utcnow().isocalendar()[1]}**:")
        output = f"```{hd[0]:<{wd}} | {hd[1]:>{len(hd[1])}}"
        output += '\n' + '-' * (len(output) - 3)
        for mchar in mchars:
            mchar.mana = random.randint(MAGIC_ROLL_RANGE[0], MAGIC_ROLL_RANGE[1])
            chunk = f"\n{mchar.name:<{wd}} | {mchar.mana:>{len(hd[1])}}"
            # ensure that the whole output isn't longer than 2000 characters
            if (len(output) + len(chunk)) > 2000:
                await channels[MAGIC_ROLLS].send(output)
                output = chunk
            else:
                output += chunk
        session.commit()
        await channels[MAGIC_ROLLS].send(output + "```")

async def update_roles():
    guild = get_guild(bot)
    while True:
        # schedule the next function call
        now = datetime.utcnow()
        date = now.date()
        if now.time() > UPDATE_ROLES_TIME:
            date = now.date() + timedelta(days=1)
        then = datetime.combine(date, UPDATE_ROLES_TIME)
        await discord.utils.sleep_until(then)
        # perfom the actual role update
        roles = get_roles(guild)

        # clan roles that are required based on the actual Characters table
        logger.info("Starting to reindex discord clan roles.")

        guild_members = {}
        for member in guild.members:
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
                logger.info(f"Deleting role {name}.")
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
                roles[name] = await guild.create_role(name=name, hoist=hoist, mentionable=mentionable)
                logger.info(f"Creating role {name}.")
                # add all members to that role
                for member in members:
                    await member.add_roles(roles[name])
                    logger.info(f"Adding {str(member)} to role {name}.")
            # update existing roles
            else:
                # add members not alread assigned to the role
                for member in members:
                    if not member in roles[name].members:
                        await member.add_roles(roles[name])
                        logger.info(f"Adding {str(member)} to role {name}.")
                # remove members that are assigned to the role but shouldn't be
                for member in roles[name].members:
                    if not member in members:
                        await member.remove_roles(roles[name])
                        logger.info(f"Removing {str(member)} from role {name}.")

        # create a positions list for the roles
        reindexed_roles = before_clan_roles + sorted(clan_roles, reverse=True) + after_clan_roles
        positions = {}
        for position in range(1, len(reindexed_roles)):
            name = reindexed_roles[position]
            positions[roles[name]] = position

        # reorder the clan roles alphabetically
        await guild.edit_role_positions(positions)
        logger.info("Finished reindexing discord clan roles.")

async def display_playerlist():
    while True:
        channels = get_channels(bot=bot)
        async for message in channels[DISPLAY_PLAYERLIST].history(limit=100):
            if message.author == bot.user:
                break
        now = datetime.utcnow()
        playerlist, success = listplayers()
        if not success:
            await discord.utils.sleep_until(now + timedelta(seconds=30))
            continue
        logger.info(f"Updated playerlist in channel {channels[DISPLAY_PLAYERLIST]}")
        await message.edit(content=f"{playerlist}\n(last update: {now:%H:%M} UTC)")
        await discord.utils.sleep_until(now + DISPLAY_PLAYERLIST_INTERVAL)

async def get_time():
    first_attempt = now = datetime.utcnow()
    failure = get_time_decimal()
    while failure and now - first_attempt <= timedelta(minutes=2, seconds=10):
        await discord.utils.sleep_until(now + timedelta(seconds=30))
        failure = get_time_decimal()
        now = datetime.utcnow()
    return

async def set_time():
    first_attempt = now = datetime.utcnow()
    failure = set_time_decimal()
    while failure and now - first_attempt <= timedelta(minutes=5, seconds=10):
        await discord.utils.sleep_until(now + timedelta(seconds=30))
        failure = set_time_decimal()
        now = datetime.utcnow()
    return

##############
''' Events '''
##############

@bot.event
async def on_ready():
    # rcon.RCONMessage.ENCODING = "utf-8"
    logger.info(f"{bot.user.name} has connected to Discord.")
    # determine discord server
    guild = get_guild(bot)
    if guild:
        logger.info(f"Discord server {guild.name} ({guild.id}) was found.")
    else:
        exit(f"{DISCORD_NAME} wasn't found. Please check cfg.py or authorize the bot.")
    # initialize checks
    init_checks(guild)
    # get all categories
    categories = get_categories(guild)
    # get all channels
    channels = get_channels(guild)
    # get all roles
    roles = get_roles(guild)
    # create channel and category if necessary
    for channel in DISCORD_CHANNELS:
        if not channel[0] in channels:
            if channel[1] and not channel[1] in categories:
                categories[channel[1]] = await guild.create_category(channel[1])
            category = categories[channel[1]] if channel[1] else None
            channels[channel[0]] = await guild.create_text_channel(channel[0], category=category)
            logger.info(f"{channel[0]} channel was created (id = {channels[channel[0]].id})")
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
    if DISPLAY_PLAYERLIST:
        display_playerlist_task = asyncio.create_task(display_playerlist())
        display_playerlist_task.add_done_callback(exception_catching_callback)
    for group in session.query(Groups).order_by(Groups.next_due).all():
        payments_task = asyncio.create_task(payments(group.id, group.category_id))
        payments_task.add_done_callback(exception_catching_callback)
    for category in session.query(Categories).all():
        payments_output_task = asyncio.create_task(payments_output(bot.guilds, category.id))
        payments_output_task.add_done_callback(exception_catching_callback)


@bot.event
async def on_member_join(member):
    logger.info(f"{member} just joined the discord.")
    guild = get_guild(bot)
    roles = get_roles(guild)
    channels = get_channels(guild)
    await member.add_roles(roles[NOT_APPLIED_ROLE])
    await channels[WELCOME].send(parse(guild, member, TextBlocks.get('GREETING')))

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
    guild = get_guild(bot)
    channels = get_channels(guild)
    if message.channel == channels[STATUS]:
        if message.content.startswith(SHUTDOWN_MSG):
            get_time_task = asyncio.create_task(get_time())
            get_time_task.add_done_callback(exception_catching_callback)

        elif message.content.startswith(RESTART_MSG):
            set_time_task = asyncio.create_task(set_time())
            set_time_task.add_done_callback(exception_catching_callback)

    for category in session.query(Categories).all():
        if message.channel.id == int(category.input_channel) and category.alert_message in message.content:
            await payments_input(category, message)

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
        await message.author.dm_channel.send(parse(guild, message.author, TextBlocks.get('APP_CLOSED')))
        return
    if app.current_question < 0:
        return
    questions = app.questions
    questions[app.current_question-1].answer = message.content
    session.commit()
    app.current_question = app.first_unanswered
    if app.current_question > 0:
        question = await Apps.get_question_msg(guild, questions, message.author, app.current_question)
        await message.author.dm_channel.send(question)
    elif not app.status == 'finished':
        app.status = 'finished'
        await message.author.dm_channel.send(parse(guild, message.author, TextBlocks.get('FINISHED')))
    session.commit()

@bot.event
async def on_command_error(ctx, error):
    # if save_d.C_ERR:
    #     save_d.C_ERR = False
    #     return
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
