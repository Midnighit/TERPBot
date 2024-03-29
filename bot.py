import os
import random
import discord
import asyncio
import exiles_api
import openai
from sqlalchemy import func
from datetime import datetime, timedelta
from discord import ChannelType
from discord.ext import commands
from cogs.applications import Applications as Apps
from logger import logger
from checks import has_role, init_checks
from exiles_api import (
    session, MagicChars, Characters, Users, Groups, Categories, TextBlocks, Applications, GlobalVars, TERPRCon
)
from functions import (
    filter_types, get_roles, get_guild, get_channels, get_categories, get_time_decimal, set_time_decimal,
    payments, payments_input, payments_output, parse, listplayers, exception_catching_callback, set_timer, is_running,
    process_pippi_chat_command, process_rr_chat_command
)
from config import (
    DURA_TYPES, HUB_ALERTS, PREFIX, DISCORD_TOKEN, DISCORD_CHANNELS, DISCORD_NAME, UPDATE_MAGIC_TIME, UPDATE_MAGIC_DAY,
    MAGIC_ROLLS, MAGIC_ROLL_RANGE, UPDATE_ROLES_TIME, CLAN_START_ROLE, CLAN_END_ROLE, CLAN_IGNORE_LIST, CLAN_ROLE_HOIST,
    CLAN_ROLE_MENTIONABLE, PLAYERLIST, DISPLAY_PLAYERLIST, ADMIN_ROLE, SUPPORT_ROLE, DM_ROLE, NOT_APPLIED_ROLE,
    SETROLES_EXPLANATION, SETROLES_REACTIONS, SETROLES, DISPLAY_SETROLES, ROLL_FOR_MANA, WELCOME, STATUS, TIME_SYNC,
    SHUTDOWN_MSG, RESTART_MSG, CHATLOG, DICELOG, IGNORE_CMDS, TIMERS, RCON_KEEP_ALIVE_TIME, RCON_IP, RCON_PASSWORD,
    RCON_PORT, STAFF_DISCORD_NAME, RR_CHAT_WEBHOOK, OPENAI_API_KEY, INACTIVITY, ACTIVE_CHAR_ROLE, UPDATE_CLAN_ROLES
)

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
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
            logger.info("No magic chars registered.")
            continue
        longest_name = session.query(func.max(func.length(MagicChars.name))).filter_by(active=True).scalar()
        hd = ["Character", " MP"]
        wd = longest_name if longest_name > len(hd[0]) else len(hd[0])
        await channels[MAGIC_ROLLS].send(
            f"Mana point rolls for calendar week **{datetime.utcnow().isocalendar()[1]}**:"
        )
        output = f"```{hd[0]:<{wd}} | {hd[1]:>{len(hd[1])}}"
        output += "\n" + "-" * (len(output) - 3)
        for mchar in mchars:
            mchar.mana = random.randint(MAGIC_ROLL_RANGE[0], MAGIC_ROLL_RANGE[1])
            chunk = f"\n{mchar.name:<{wd}} | {mchar.mana:>{len(hd[1])}}"
            # ensure that the whole output isn't longer than 1800 characters
            if (len(output) + len(chunk)) > 1800:
                await channels[MAGIC_ROLLS].send(output)
                output = chunk
            else:
                output += chunk
        session.commit()
        await channels[MAGIC_ROLLS].send(output + "```")


async def update_roles():
    guild = get_guild(bot)
    if UPDATE_ROLES_TIME is False:
        return

    if not (UPDATE_CLAN_ROLES or ACTIVE_CHAR_ROLE):
        return

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
        # get all characters
        characters = session.query(Characters)

        if UPDATE_CLAN_ROLES:
            # clan roles that are required based on the actual Characters table
            logger.info("Starting to reindex discord clan roles.")

            guild_members = {}
            for member in guild.members:
                guild_members[str(member.id)] = member

            required_clan_roles = {}
            for char in characters:
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
                    if disc_id not in guild_members:
                        logger.info(f"Couldn't get member by DiscordID for {char.name} for clan roles indexing")
                        continue
                    member = guild_members[disc_id]
                    if guild_name not in required_clan_roles:
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

            before_clan_roles = roles_idx[: end_pos + 1]
            after_clan_roles = roles_idx[start_pos:]

            # create a slice of only those guilds that are actually required
            clan_roles = []
            for name in sorted(roles_idx[end_pos + 1:start_pos]):
                # remove existing roles that are no longer required
                if name not in required_clan_roles:
                    await roles[name].delete()
                    del roles[name]
                    logger.info(f"Deleting role {name}.")
                # create the slice of existing clans otherwise
                else:
                    clan_roles.append(name)

            # add roles and update their members as required
            for name, members in required_clan_roles.items():
                # add clan roles not existing yet
                if name not in roles:
                    clan_roles.append(name)
                    hoist = CLAN_ROLE_HOIST
                    mentionable = CLAN_ROLE_MENTIONABLE
                    roles[name] = await guild.create_role(name=name, hoist=hoist, mentionable=mentionable)
                    logger.info(f"Creating role {name}.")
                    # add all members to that role
                    for member in members:
                        await member.add_roles(roles[name])
                        logger.info(f"Adding {member.name} to role {name}.")
                # update existing roles
                else:
                    # add members not alread assigned to the role
                    for member in members:
                        if member not in roles[name].members:
                            await member.add_roles(roles[name])
                            logger.info(f"Adding {member.name} to role {name}.")
                    # remove members that are assigned to the role but shouldn't be
                    for member in roles[name].members:
                        if member not in members:
                            await member.remove_roles(roles[name])
                            logger.info(f"Removing {member.name} from role {name}.")

            # create a positions list for the roles
            reindexed_roles = before_clan_roles + sorted(clan_roles, reverse=True) + after_clan_roles
            positions = {}
            for position in range(1, len(reindexed_roles)):
                name = reindexed_roles[position]
                positions[roles[name]] = position

            # reorder the clan roles alphabetically
            await guild.edit_role_positions(positions)
            logger.info("Finished reindexing discord clan roles.")

        if ACTIVE_CHAR_ROLE:
            # update the active role
            logger.info("Starting to update discord active roles.")
            active_role = roles[ACTIVE_CHAR_ROLE]
            users = {user.disc_id: user.characters for user in session.query(Users).all() if len(user.characters) > 0}
            for member in guild.members:
                # discord_id found in users
                if str(member.id) in users:
                    chars = users[str(member.id)]
                    # member has active chars but not the active role
                    if chars.active(INACTIVITY) and active_role not in member.roles:
                        await member.add_roles(active_role)
                        logger.info(f"Adding {member.name} ({member.id}) to role {active_role.name}.")
                    # member has the active role but no active chars
                    elif not chars.active(INACTIVITY) and active_role in member.roles:
                        await member.remove_roles(active_role)
                        logger.info(f"Removing {member.name} ({member.id}) from role {active_role.name}.")
                # member has no char or user is not on the list
                elif active_role in member.roles:
                    await member.remove_roles(active_role)
                    logger.info(f"Removing {member.name} ({member.id}) from role {active_role.name}.")

            logger.info("Finished updating discord active roles.")


async def display_playerlist():
    while True:
        channels = get_channels(bot=bot)
        message = None
        async for message in channels[PLAYERLIST].history(limit=100):
            if message.author == bot.user:
                break

        now = datetime.utcnow()
        playerlist, success = await listplayers()
        if not success:
            await discord.utils.sleep_until(now + timedelta(seconds=30))
            continue

        if message:
            await message.edit(content=f"{playerlist}\n(last update: {now:%H:%M} UTC)")
        else:
            await channels[PLAYERLIST].send(f"{playerlist}\n(last update: {now:%H:%M} UTC)")
        await discord.utils.sleep_until(now + DISPLAY_PLAYERLIST)


async def get_time():
    first_attempt = now = datetime.utcnow()
    failure = await get_time_decimal()
    while failure and now - first_attempt <= timedelta(minutes=2, seconds=10):
        await discord.utils.sleep_until(now + timedelta(seconds=30))
        failure = await get_time_decimal()
        now = datetime.utcnow()
    return


async def set_time():
    first_attempt = now = datetime.utcnow()
    failure = await set_time_decimal()
    while failure and now - first_attempt <= timedelta(minutes=5, seconds=10):
        await discord.utils.sleep_until(now + timedelta(seconds=30))
        failure = await set_time_decimal()
        now = datetime.utcnow()
    return


async def set_roles(channels):
    content = SETROLES_EXPLANATION + "\n"
    for emoji, data in SETROLES_REACTIONS.items():
        content += data["descr"] + "\n"
    found = None
    async for message in channels[SETROLES].history(limit=100):
        if message.author == bot.user:
            found = message
            await message.edit(content=content)
            break
    if not found:
        message = await channels[SETROLES].send(content)
    for emoji, data in SETROLES_REACTIONS.items():
        await message.add_reaction(emoji)


async def keep_trc_alive():
    """ Task to start and keep the MCRcon connection alive as trc object within bot.py. """
    exiles_api.trc = TERPRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)
    exiles_api.trc.last_cmd = 0
    while True:
        last_cmd = datetime.fromtimestamp(float(GlobalVars.get_value('LAST_CMD')))
        time_passed = datetime.utcnow() - last_cmd

        # if server isn't running, there's no need to try and connect trc.
        if not is_running():
            if exiles_api.trc and exiles_api.trc.is_connected:
                try:
                    logger.debug('trying to close trc connection.')
                    await exiles_api.trc.close()
                    logger.debug('closed trc connection.')
                except Exception:
                    logger.debug('failed closing trc connection.')
                logger.debug('setting trc to None')
                exiles_api.trc = None
            await asyncio.sleep(1)

        # server is running but trc hasn't been created yet or has subsequently been set to None again
        elif not exiles_api.trc:
            logger.debug('trying to instantiate and connect a new trc object.')
            try:
                exiles_api.trc = TERPRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)
                await exiles_api.trc.connect()
                logger.debug(f'connection established. Waiting for {RCON_KEEP_ALIVE_TIME.seconds} seconds.')
                await asyncio.sleep(RCON_KEEP_ALIVE_TIME.seconds)
            except Exception:
                logger.debug('failed to create object and connection trying again in 10 seconds.')
                await asyncio.sleep(10)

        # server is running, trc object is instantiated but connection isn't ready
        elif not exiles_api.trc.is_connected:
            logger.debug('trying to connect trc object')
            try:
                await exiles_api.trc.connect()
                exiles_api.trc.last_cmd = datetime.timestamp(datetime.utcnow())
                logger.debug(f'connection established. Waiting for {RCON_KEEP_ALIVE_TIME.seconds} seconds.')
            except Exception as error:
                logger.debug(f'failed to create connection trying again in 10 seconds. {str(error)}')
                await asyncio.sleep(10)

        # server is running, trc object is instantiated and connected
        else:
            if time_passed < RCON_KEEP_ALIVE_TIME:
                await asyncio.sleep(1)
            else:
                msg, success = await exiles_api.trc.safe_send_cmd("help")
                if success:
                    logger.debug(f'keeping connection alive. Waiting for {RCON_KEEP_ALIVE_TIME.seconds} seconds.')
                else:
                    logger.debug('failed to keep connection alive.')
                    try:
                        logger.debug('trying to close trc connection.')
                        await exiles_api.trc.close()
                        logger.debug('closed trc connection.')
                    except Exception:
                        logger.debug('failed closing trc connection.')
                    logger.debug('setting trc to None')
                    exiles_api.trc = None


##############
""" Events """
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
    openai.api_key = OPENAI_API_KEY
    # load cogs
    for filename in os.listdir("cogs"):
        if filename.endswith(".py"):
            bot.load_extension(f"cogs.{filename[:-3]}")
    keep_trc_alive_task = asyncio.create_task(keep_trc_alive())
    keep_trc_alive_task.add_done_callback(exception_catching_callback)
    if UPDATE_ROLES_TIME:
        update_roles_task = asyncio.create_task(update_roles())
        update_roles_task.add_done_callback(exception_catching_callback)
    if ROLL_FOR_MANA:
        magic_roles_task = asyncio.create_task(magic_rolls())
        magic_roles_task.add_done_callback(exception_catching_callback)
    if DISPLAY_PLAYERLIST:
        display_playerlist_task = asyncio.create_task(display_playerlist())
        display_playerlist_task.add_done_callback(exception_catching_callback)
    if DISPLAY_SETROLES:
        await set_roles(channels)
    for group in session.query(Groups).order_by(Groups.next_due).all():
        payments_task = asyncio.create_task(payments(group.id, group.category_id))
        payments_task.add_done_callback(exception_catching_callback)
    for category in session.query(Categories).filter(Categories.verbosity != 0).all():
        payments_output_task = asyncio.create_task(payments_output(bot.guilds, category.id))
        payments_output_task.add_done_callback(exception_catching_callback)
    timers = GlobalVars.get_value("TIMERS")
    timers = eval(timers) if timers else {}
    for name, timer in timers.items():
        set_timer_task = asyncio.create_task(set_timer(name, timer, bot.guilds))
        set_timer_task.add_done_callback(exception_catching_callback)


@bot.event
async def on_member_join(member):
    logger.info(f"{member} just joined the discord.")
    guild = get_guild(bot)
    roles = get_roles(guild)
    channels = get_channels(guild)
    await member.add_roles(roles[NOT_APPLIED_ROLE])
    await channels[WELCOME].send(parse(guild, member, TextBlocks.get("GREETING")))


@bot.event
async def on_member_remove(member):
    channels = get_channels(bot=bot)
    if SETROLES in channels:
        async for message in channels[SETROLES].history(limit=100):
            if message.author == bot.user:
                break
        if message:
            for reaction in message.reactions:
                async for user in reaction.users():
                    if user.id == member.id:
                        await reaction.remove(user)
    app = session.query(Applications).filter_by(disc_id=member.id).first()
    if app and app.status not in ("rejected", "approved"):
        session.delete(app)
        session.commit()
        logger.info(f"{member} just left discord. Ongoing application was cancelled")
    else:
        logger.info(f"{member} just left discord.")


@bot.event
async def on_message(message):
    guild = get_guild(bot)
    channels = get_channels(guild)
    staff_roles = get_roles(bot=bot, name=STAFF_DISCORD_NAME)
    if TIME_SYNC and message.channel == channels[STATUS]:
        if message.content.startswith(SHUTDOWN_MSG):
            get_time_task = asyncio.create_task(get_time())
            get_time_task.add_done_callback(exception_catching_callback)

        elif message.content.startswith(RESTART_MSG):
            set_time_task = asyncio.create_task(set_time())
            set_time_task.add_done_callback(exception_catching_callback)

    if TIMERS and message.channel.id == HUB_ALERTS and ' has purchased a ' in message.content:
        location, rest = message.content.split(': ', 1)
        char_name, rest = rest.split(' has purchased a ')
        duration, _ = rest.split(' permit.')
        result, _ = filter_types(duration, DURA_TYPES)
        seconds = 0
        for type, amount in result.items():
            if type == 'seconds':
                seconds += amount
            elif type == 'minutes':
                seconds += amount * 60
            elif type == 'hours':
                seconds += amount * 60 * 60
            elif type == 'days':
                seconds += amount * 24 * 60 * 60
            else:
                seconds += amount * 7 * 24 * 60 * 60
        now = datetime.utcnow()
        end = (now + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")
        name = f'{location}-{char_name}-{now.strftime("%H:%M")}-permit'
        msg = (
            f'It is now **{end}** and timer **{name}** has just run out. '
            f'{staff_roles[SUPPORT_ROLE].mention} {staff_roles[DM_ROLE].mention}.'
        )
        timer = {'end': end, 'channel': HUB_ALERTS, 'mention': 0, 'message': msg}
        chars = Characters.get_by_name(char_name, include_guilds=False)
        if len(chars) == 1 and chars[0].user and chars[0].user.disc_id:
            timer['owner'] = int(chars[0].user.disc_id)

        set_timer_task = asyncio.create_task(set_timer(name, timer, bot.guilds))
        set_timer_task.add_done_callback(exception_catching_callback)
        logger.info(f'**{name}** timer started. It will finish at **{end} UTC**.')
        await message.channel.send(f'**{name}** timer started. It will finish at **{end} UTC**.')

    for category in session.query(Categories).all():
        if message.channel.id == int(category.input_channel) and category.alert_message in message.content:
            await payments_input(category, message)

    app = session.query(Applications).filter_by(disc_id=message.author.id).first()
    if message.channel == channels[CHATLOG]:
        if " executed chat command " in message.content:
            await process_pippi_chat_command(message.content)
    elif message.channel == channels[DICELOG]:
        if message.author.id == RR_CHAT_WEBHOOK:
            await process_rr_chat_command(message.content)

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
    if app and app.status in ("rejected", "accepted"):
        return
    if not app or not app.can_edit_questions():
        await message.author.dm_channel.send(parse(guild, message.author, TextBlocks.get("APP_CLOSED")))
        return
    if app.current_question < 0:
        return
    questions = app.questions
    questions[app.current_question - 1].answer = message.content
    session.commit()
    app.current_question = app.first_unanswered
    if app.current_question > 0:
        question = await Apps.get_question_msg(guild, questions, message.author, app.current_question)
        await message.author.dm_channel.send(question)
    elif not app.status == "finished":
        app.status = "finished"
        await message.author.dm_channel.send(parse(guild, message.author, TextBlocks.get("FINISHED")))
    session.commit()


@bot.event
async def on_raw_reaction_add(payload):
    if DISPLAY_SETROLES:
        guild = get_guild(bot)
        channels = get_channels(guild)
        roles = get_roles(guild)
        if payload.emoji.name in SETROLES_REACTIONS and payload.channel_id == channels[SETROLES].id:
            reaction = SETROLES_REACTIONS[payload.emoji.name]
            name = reaction["role"]
            if name not in roles:
                mentionable = reaction["mentionable"] if "mentionable" in reaction else False
                roles[name] = await guild.create_role(name=name, mentionable=mentionable)
            await payload.member.add_roles(roles[name])


@bot.event
async def on_raw_reaction_remove(payload):
    if DISPLAY_SETROLES:
        guild = get_guild(bot)
        channels = get_channels(guild)
        roles = get_roles(guild)
        if payload.emoji.name in SETROLES_REACTIONS and payload.channel_id == channels[SETROLES].id:
            reaction = SETROLES_REACTIONS[payload.emoji.name]
            name = reaction["role"]
            if name in roles:
                for member in guild.members:
                    if roles[name] in member.roles and member.id == payload.user_id:
                        await member.remove_roles(roles[name])
                        break


@bot.event
async def on_command_error(ctx, error):
    if int(GlobalVars.get_value("CAUGHT")):
        GlobalVars.set_value("CAUGHT", 0)
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("Bad argument error.")
    elif isinstance(error, commands.CommandError):
        await ctx.send(error)
    else:
        await ctx.send("Unknown error. Please check the logs for details.")
    if hasattr(error, "args"):
        for arg in error.args:
            if isinstance(arg, str):
                error = arg
                break
    logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {str(error)}")


@bot.command(hidden=True)
@has_role(ADMIN_ROLE)
async def reload(ctx, extension):
    bot.reload_extension(f"cogs.{extension}")
    await ctx.send(f"Cog {extension} has been reloaded.")


bot.run(DISCORD_TOKEN)
