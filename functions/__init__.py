import re
import discord
import asyncio
import itertools
import pprint
import exiles_api
import json
from discord import Member
from discord.ext import commands
from datetime import timedelta, datetime
from logger import logger
from exiles_api import (
    session, next_time, adjusted_next_due, is_running, Owner, Guilds, Characters,
    Users, Groups, CatOwners, Categories, OwnersCache, GlobalVars
)
from config import DISCORD_NAME, SUPPORT_ROLE, PREFIX, WHITELIST_PATH, SAVED_DIR_PATH


def pp(arg):
    printer = pprint.PrettyPrinter(indent=4)
    printer.pprint(arg)


def pe(arg):
    print("error: " + arg)
    print(" type: " + type(arg))
    print("  dir: ")
    pp(dir(arg))


def get_guild(bot=None, guild=None, name=DISCORD_NAME):
    if guild:
        return guild
    elif bot:
        return discord.utils.get(bot.guilds, name=name)
    else:
        logger.error("Called get_guild() but passed neither bot nor guild.")
        return None


def get_categories(guild=None, bot=None, name=DISCORD_NAME):
    guild = get_guild(bot, guild, name)
    if guild:
        return {category.name: category for category in guild.categories}
    return None


def get_channels(guild=None, bot=None, name=DISCORD_NAME):
    guild = get_guild(bot, guild, name)
    if guild:
        return {channel.name: channel for channel in guild.channels}
    logger.error("Called get_channels() but passed neither bot nor guild.")
    return None


def get_roles(guild=None, bot=None, name=DISCORD_NAME):
    guild = get_guild(bot, guild, name)
    if guild:
        return {role.name: role for role in guild.roles}
    logger.error("Called get_roles() but passed neither bot nor guild.")
    return None


def has_support_role_or_greater(guild, author):
    roles = get_roles(guild)
    member = guild.get_member(author.id)
    for author_role in member.roles:
        if author_role >= roles[SUPPORT_ROLE]:
            return True


def get_chars_by_user(user):
    user = session.query(Users).filter_by(disc_id=user.id).first()
    if not user:
        return []
    return user.characters


def parse(guild, user=None, msg=''):
    channels = get_channels(guild)
    roles = get_roles(guild)
    msg = str(msg).replace("{PREFIX}", PREFIX).replace("{OWNER}", guild.owner.mention)
    if user:
        msg = msg.replace("{PLAYER}", user.mention) if isinstance(user, Member) else msg.replace("{PLAYER}", str(user))
    for name, channel in channels.items():
        msg = re.sub("(?i){" + name + "}", channel.mention, msg)
    for name, role in roles.items():
        msg = re.sub("(?i){" + name + "}", role.mention, msg)
    return msg


def is_hex(s):
    return all(c in "1234567890ABCDEF" for c in s.upper())


def is_float(s):
    return re.match(r"^-?\d+(?:\.\d+)?$", s) is not None


def rreplace(s, old, new):
    li = s.rsplit(old, 1)
    return new.join(li)


def is_time_format(time):
    tLst = time.split(":")
    if not tLst:
        return False

    if len(tLst) >= 1 and tLst[0].isnumeric() and int(tLst[0]) >= 0:
        hours = str(int(tLst[0]) % 24)
    else:
        return False

    if len(tLst) >= 2 and tLst[1].isnumeric() and int(tLst[1]) >= 0 and int(tLst[1]) < 60:
        minutes = tLst[1]
    elif len(tLst) < 2:
        minutes = "00"
    else:
        return False

    if len(tLst) >= 3 and tLst[2].isnumeric() and int(tLst[2]) >= 0 and int(tLst[2]) < 60:
        seconds = tLst[2]
    elif len(tLst) < 3:
        seconds = "00"
    else:
        return False

    return ":".join([hours, minutes, seconds])


def is_on_whitelist(funcom_id):
    try:
        with open(WHITELIST_PATH, "rb") as f:
            line = f.readline()
            codec = "utf16" if line.startswith(b"\xFF\xFE") else "utf8"
    except Exception:
        return False
    try:
        with open(WHITELIST_PATH, "r", encoding=codec) as f:
            lines = f.readlines()
    except Exception:
        return False
    funcom_id = funcom_id.upper()
    for line in lines:
        if funcom_id in line.upper():
            return True
    return False


def update_whitelist_file(funcom_id, add=True):
    whitelisted = is_on_whitelist(funcom_id)
    if (whitelisted and add) or (not whitelisted and not add):
        return
    # determine codec
    try:
        with open(WHITELIST_PATH, "rb") as f:
            line = f.readline()
            codec = "utf16" if line.startswith(b"\xFF\xFE") else "utf8"
    except Exception:
        codec = "utf8"
    try:
        with open(WHITELIST_PATH, "r", encoding=codec) as f:
            lines = f.readlines()
    except Exception:
        with open(WHITELIST_PATH, "w") as f:
            pass
        lines = []
    # removed duplicates and lines with INVALID. Ensure that each line ends with a newline character
    filtered = set()
    names = {}
    # define regular expression to filter out unprintable characters
    control_chars = "".join(map(chr, itertools.chain(range(0x00, 0x20), range(0x7F, 0xA0))))
    control_char_re = re.compile("[%s]" % re.escape(control_chars))
    for line in lines:
        if line != "\n" and "INVALID" not in line and (add or funcom_id not in line):
            # remove unprintable characters from the line
            res = control_char_re.sub("", line)
            res = res.split(":")
            id = res[0].strip()
            if len(res) > 1:
                name = res[1].strip()
            else:
                name = "Unknown"
            filtered.add(id)
            if id not in names or names[id] == "Unknown":
                names[id] = name
    if add:
        filtered.add(funcom_id)
    names[funcom_id] = "Unknown"
    wlist = []
    for id in filtered:
        wlist.append(id + ":" + names[id] + "\n")
    wlist.sort()
    with open(WHITELIST_PATH, "w") as f:
        f.writelines(wlist)


def split_message(message, delimiter="\n"):
    result = []
    # if message is longer than 1800 chars, split it at the delimiter
    while len(message) > 1800:
        # get the closest delimiter to the 1800 chars and split the message there.
        # the first part is appended to the result list
        result.append(message[0:message.rfind(delimiter, 0, 1800)])
        # the second part becomes the new message
        message = message[message.rfind(delimiter, 0, 1800) + 1:]

    # the leftover message becomes the last part of the list
    result.append(message)

    return result


def format_timedelta(delta, fmt='**'):
    total_seconds = delta.seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    ret = {
        'days': delta.days,
        'hours': hours,
        'minutes': minutes,
        'seconds': seconds,
        'days_str': 'days' if delta.days != 1 else 'day',
        'hours_str': 'hours' if hours != 1 else 'hour',
        'minutes_str': 'minutes' if minutes != 1 else 'minute',
        'seconds_str': 'seconds' if seconds != 1 else 'second'
    }
    str_list = []
    if delta.days != 0:
        str_list.append(f'{fmt}{delta.days}{fmt} {ret["days_str"]}')
    if hours != 0:
        str_list.append(f'{fmt}{hours}{fmt} {ret["hours_str"]}')
    if minutes != 0:
        str_list.append(f'{fmt}{minutes}{fmt} {ret["minutes_str"]}')
    if seconds != 0:
        str_list.append(f'{fmt}{seconds}{fmt} {ret["seconds_str"]}')
    if len(str_list) > 2:
        start = ', '.join(str_list[:-1])
    else:
        start = str_list[0]
    if len(str_list) > 1:
        ret['full_str'] = f'{start} and {str_list[-1]}'
    elif len(str_list) == 1:
        ret['full_str'] = str_list[0]
    else:
        ret['full_str'] = ''

    return ret


def filter_types(args, types):
    """
    Parses an argument string for a given set of types that are have leading number values and tallies them up.
    The types are given as a dict consisting of searchstring: target_dict_key.
    Returns a tuble consisting of the filter argument string and a dict with the tallied values by target_dict_key.
    example:
    args == 'set MyTimer 5 h 20 m 30 sec'
    types == {
        'hours': 'hours', 'hour': 'hours', 'hrs': 'hours', 'h': 'hours',
        'minutes': 'minutes', 'minute': 'minutes', 'min': 'minutes', 'm': 'minutes',
        'seconds': 'seconds', 'second': 'seconds', 'sec': 'seconds', 's': 'seconds'
    }
    returns == ({'hours': 5, 'minutes': 20, 'seconds': 30}, 'set MyTimer')
    """

    # split argument string into a list of arguments
    arg_list = args.split()
    results = {}
    rem = []
    idx, prev = 0, None

    # go through all arguments
    for arg in arg_list:
        # check current argument for each type
        for type, key in types.items():
            # if arg matches a type and it's following another argument and that argument is numeric
            if type == arg.lower() and prev and prev.isnumeric():
                results[key] = int(prev) if key not in results else results[key] + int(prev)
                # append index of amount and type arguments to rem for later deletion
                rem += [idx-1, idx]
            elif arg.lower().endswith(type) and arg.lower()[0:-len(type)].isnumeric():
                amount = int(arg.lower()[0:-len(type)])
                results[key] = amount if key not in results else results[key] + amount
                # append index of combined amount and type argument to rem for later deletion
                rem += [idx]

        prev = arg
        idx += 1

    # traverse the removal list backwards to ensure the indices remain the same after deletion
    for idx in reversed(rem):
        del arg_list[idx]

    remainder = " ".join(arg_list)
    return (results, remainder)


async def set_timer(name, timer, guilds):
    """
    sets a timer using discord.utils.sleep_until function and
    stores it in the db to ensure it's persistent through bot restarts.
    name: the name of the timer to allow for multiple timers
    timer: dict that stores the timer attributes.
        Required attributes:
            channel: the channel that the finished timer should be announced to
            end: the datetime at which the timer should be resolved
        Optional attributes:
            owner: the discord_id of the owner of the timer.
            mention: set to 1 to ping owner 0 otherwise. Is assumed to be 1 if not given.
            message: message to send once the timer runs out. A default message is sent if no message is given.
    message: the message to be sent when timere finishes
    """
    # timers is a dict of dicts that describe all the various timers
    # e.g. timers["tea-time"] = {"end": "2021-12-19 17:00", "channel": "hub-alerts"}
    value = GlobalVars.get_value('TIMERS')
    # the mention setting only works if owner is also given

    mention = timer.get('mention', 1) and 'owner' in timer

    # confirm some necessary keys are set
    if not('end' in timer and 'channel' in timer):
        return None
    # if no timers exist, create a new one.
    if not value:
        timers = {}
        timers[name] = timer
    # otherwise add a new one or overwrite an existing one with the same name.
    else:
        timers = eval(value)
        timers[name] = timer
    # save updated timers value
    GlobalVars.set_value("TIMERS", str(timers))

    # delete gv variable to ensure it's not reused after sleep.
    del value

    # wait until the given datetime
    await discord.utils.sleep_until(datetime.strptime(timer['end'], "%Y-%m-%d %H:%M:%S"))

    # re-read the timers from the database to delete the given timer
    value = GlobalVars.get_value('TIMERS')
    # remove timer from timers dict
    if value:
        timers = eval(value)
        if name in timers:
            del timers[name]
            GlobalVars.set_value("TIMERS", str(timers))

    # message is either the given message or a default
    message = timer.get('message', f"It is now **{timer['end']}** and timer **{name}** has just run out.")

    # determine the channel and owner - if available
    o, c = None, None
    for guild in guilds:
        # skip owner detection if mention is disabled
        if mention:
            for member in guild.members:
                if member.id == timer['owner']:
                    o = member
                    break
        for channel in guild.channels:
            if channel.id == int(timer['channel']):
                c = channel
                break
        # stop searching if either owner and channel were found or only channel if mention has been disabled
        if (o and c) or (c and not mention):
            break

    if mention and o and c:
        await c.send(f'{o.mention} {message}')
    elif c:
        await c.send(message)
    elif o:
        await o.send(message)
    else:
        return None

    return True


async def get_member(ctx, name):
    if name is not str:
        name = str(name)
    try:
        return await commands.MemberConverter().convert(ctx, name)
    except Exception:
        try:
            return await commands.MemberConverter().convert(ctx, name.capitalize())
        except Exception:
            return None


async def get_category_msg(category, messages=[]):
    groups = [g for g in session.query(Groups).filter_by(category=category).all()]
    if len(groups) == 0:
        return messages
    groups.sort(key=lambda owner: owner.name)
    type = "Clans" if category.guild_pay else "Characters"
    chunk = f"__**{type}** and groups in category **{category.cmd}**:__\n"
    msgs = []
    if len(messages) > 0:
        if len(messages[-1] + "\n" + chunk) <= 1800:
            chunk = messages[-1] + "\n" + chunk
            msgs = messages[:-1]
    fmt = "%A %d-%b-%Y %H:%M UTC"
    now = datetime.utcnow()
    for group in groups:
        name = group.name
        last_pay = group.last_payment.strftime(fmt) if group.last_payment else "Never"
        line = f"**{name}:**\nLast payment: {last_pay}.\n"
        next_due = adjusted_next_due(group.next_due, group.category.mode, group.balance)
        if now < next_due:
            line += f'Next due: **{next_due.strftime(fmt)}**\n'
        elif group.balance == -1:
            line += f'Was due: **{next_due.strftime(fmt)}** (1 period behind).\n'
        else:
            line += f'Was due: **{next_due.strftime(fmt)}** ({abs(group.balance)} periods behind).\n'

        if len(chunk + line) > 1800:
            msgs.append(chunk)
            chunk = line
        else:
            chunk += line
    msgs.append(chunk)
    return msgs


async def get_user_msg(groups, messages=[]):
    chunk, msgs = "", []
    if len(messages) > 0:
        if len(messages[-1] + chunk) <= 1800:
            chunk = messages[-1] + chunk
            msgs = messages[:-1]
    fmt = "%A %d-%b-%Y %H:%M UTC"
    now = datetime.utcnow()
    for group in groups:
        last_pay = group.last_payment.strftime(fmt) if group.last_payment else "Never"
        next_due = adjusted_next_due(group.next_due, group.category.mode, group.balance)
        line = f"**{group.name}** last paid their **{group.category.name}** on **{last_pay}**.\n"
        if now < next_due:
            line += f"Next payment is due on **{next_due.strftime(fmt)}**.\n"
        else:
            periods = 'periods behind' if group.balance < -1 else 'period behind'
            line += f'Last payment **was** due on **{next_due.strftime(fmt)}** ({abs(group.balance)} {periods}).\n'
        if len(chunk + line) > 1800:
            msgs.append(chunk)
            chunk = line
        else:
            chunk += line
    if chunk != "":
        msgs.append(chunk)
    return msgs


async def payments(id, category_id):
    while True:
        messaged = False
        # quit task if group has been deleted
        group = session.query(Groups).get(id)
        if not group:
            name = session.query(OwnersCache.name).filter_by(id=id).scalar()
            guess = "(" + name + ") " if name else ""
            logger.info(f"Group with id {id} {guess}no longer exists. Task has not been renewed.")
            break
        # remove characters and clans from groups if they no longer exist
        for cat_owner in group.owners:
            if not Owner.get(cat_owner.id):
                name = session.query(OwnersCache.name).filter_by(id=cat_owner.id).scalar()
                guess = "(" + name + ") " if name else ""
                logger.info(
                    f"Character or clan with id {id} {guess} and category_id {category_id} removed "
                    f"from payments list because they have been deleted from db since last time."
                )
                messaged = True
                session.delete(cat_owner)
        # remove simple groups that are empty
        if (group.is_simple and messaged and len(group.owners) <= 1) or (not messaged and len(group.owners) == 0):
            if not messaged:
                logger.info(
                    f"Character or clan with id {id} and category_id {category_id} removed "
                    f"from payments list because they have been deleted from db since last time."
                )
            session.delete(group)
        await discord.utils.sleep_until(group.next_due)
        group.balance -= 1
        group.next_due = adjusted_next_due(group.next_due, group.category.mode, 1)
        logger.info(
            f"Deducted 1 bpp from {group.name} ({id}). New balance is {group.balance}. "
            f"Next due date has been set to {group.next_due.strftime('%A %d-%b-%Y %H:%M UTC')}."
        )
        session.commit()


async def print_payments_msg(ctx, messages):
    if messages == []:
        await ctx.send("There are no characters, clans or groups registered.")
    for idx in range(len(messages)):
        if idx == len(messages) - 1 and messages[idx][-2:] == "\n":
            await ctx.send(messages[idx][:-2])
        else:
            await ctx.send(messages[idx])


async def payments_output(guilds, id):
    next_due = None
    while True:
        # confirm that user still exists otherwise break
        cat = session.query(Categories).get(id)
        if not cat:
            logger.info(
                f"Category with id {id} removed from payments list "
                f"because they have been deleted from db since last time."
            )
            break
        if cat.verbosity == 0:
            break
        frequency, _, _ = cat.mode.split(';')
        if frequency in ('monthly', 'weekly'):
            delay = timedelta(days=1) + timedelta(seconds=cat.id * 5)
        elif frequency == 'daily':
            delay = timedelta(hours=12) + timedelta(seconds=cat.id * 5)
        elif frequency == 'hourly':
            delay = timedelta(minutes=30) + timedelta(seconds=cat.id * 5)
        else:
            break

        next_due = next_time(cat.mode) - delay
        if next_due <= datetime.utcnow():
            next_due = adjusted_next_due(next_due, cat.mode, 1)
        await discord.utils.sleep_until(next_due)
        for guild in guilds:
            for channel in guild.channels:
                if channel.id == int(cat.output_channel):
                    messages = await get_category_msg(cat)
                    await print_payments_msg(channel, messages)


async def payments_input(category, message):
    cat_owners, cat_owner_ids, found = {}, [], False
    filter = (CatOwners.group_id == Groups.id) & (Groups.category_id == category.id)
    for cat_owner in session.query(CatOwners).filter(filter).all():
        cat_owner_ids.append(cat_owner.id)
        cat_owners[cat_owner.id] = cat_owner
    if category.guild_pay:
        for guild in session.query(Guilds).filter(Guilds.id.in_(cat_owner_ids)).all():
            if found:
                break
            cat_owner = cat_owners[guild.id]
            group = cat_owner.group
            if message.content == f"{guild.name} {category.alert_message}":
                found = True
                group.balance += 1
                group.last_payment = datetime.utcnow()
                logger.info(f"Added 1 bpp to {group.name} ({group.id}).")
            else:
                for char in guild.members:
                    if message.content == f"{char.name} {category.alert_message}":
                        found = True
                        cat_owner.balance += 1
                        cat_owner.last_payment = datetime.utcnow()
                        logger.info(f"Added 1 bpp to {group.name} ({group.id}).")
    # even with guild_pay set, check for character_ids when no guild or guild member was found
    if not found:
        for char in session.query(Characters).filter(Characters.id.in_(cat_owner_ids)).all():
            if found:
                break
            cat_owner = cat_owners[char.id]
            if message.content == f"{char.name} {category.alert_message}":
                group = cat_owner.group
                found = True
                group.balance += 1
                group.last_payment = datetime.utcnow()
                logger.info(f"Added 1 bpp to {group.name} ({group.id}).")

        if not found:
            logger.info(
                f"Found payments message '{message.content}' "
                f"but no character or guild named {group.name} ({group.id})."
            )

    session.commit()


async def process_pippi_chat_command(message):
    first, second = message.split(" executed chat command ")
    command, params = second.split("  with params ")
    name = first[7:]
    command = command[1:-1]
    params = params[1:-1]
    file = 'Chat'
    now = datetime.utcnow().strftime("%Y.%m.%d-%H.%M.%S:%f")[:-3]
    data = {'datetime': now, 'name': name}
    if command == "me":
        data['channel'] = 'Say'
        data['type'] = 'Chat'
        data['content'] = f"{name} {params}"
    elif command == "do":
        data['channel'] = 'Say'
        data['type'] = 'Chat'
        data['content'] = f"{params} {name}"
    elif command == "shout":
        data['channel'] = 'Yell'
        data['type'] = 'Chat'
        data['content'] = f"{name} shouts: {params}"
    elif command == "mumble":
        data['channel'] = 'Mumble'
        data['type'] = 'Chat'
        data['content'] = f"{name} mumbles: {params}"
    else:
        file = 'Commands'
        data['command'] = command
        data['type'] = 'PippiCommand'
        data['params'] = params
    try:
        with open(SAVED_DIR_PATH + "/Logs/" + file + ".log", "a", encoding="utf-8-sig") as f:
            f.write(json.dumps(data, separators=(',', ':')) + '\n')
    except Exception as e:
        print(e)


async def process_rr_chat_command(message):
    pattern = r'\:([\w]+): \[[\d:]+\]\[([\w]+)\] ([^:]+): (.*)'
    file = 'Chat'
    trans = {'mega': 'Chat', 'game_die': 'Attribute', 'muscle': 'Ability'}
    try:
        type, channel, name, content = re.search(pattern, message).groups()
    except Exception:
        file = 'Unhandled'

    try:
        if file == 'Chat':
            now = datetime.utcnow().strftime("%Y.%m.%d-%H.%M.%S:%f")[:-3]
            content = ' '.join(content.split('\n'))
            type = trans[type]
            data = {'datetime': now, 'name': name, 'channel': channel, 'type': type, 'content': content}
            with open(SAVED_DIR_PATH + "/Logs/Chat.log", "a", encoding="utf-8-sig") as f:
                f.write(json.dumps(data, separators=(',', ':')) + '\n')
        else:
            with open(SAVED_DIR_PATH + "/Logs/Unhandled.log", "a", encoding="utf-8-sig") as f:
                f.write(message + '\n')
    except Exception as e:
        print(e)


async def listplayers():
    # repeat is set to True for the first iteration
    repeat = True
    while repeat:
        # the working assumption is that no repetition is required
        repeat = False
        if exiles_api.trc:
            result, success = await exiles_api.trc.safe_send_cmd("ListPlayers")
        else:
            return "Server is not running right now, please try again later.", False

        # if playerlisting fails because there was still a previous rcon result cached try again after 1 second
        if not success and result.endswith(' added to whitelist.') or result.endswith(' removed from whitelist.'):
            repeat = True
            await asyncio.sleep(1)

    if not success:
        return result, success

    lines = result.split("\n")
    list, names = [], []
    name, level, guild, rank, disc_user = "Char name", "Level", "Clan name", "Rank", "Discord"
    ln, ll, lg, lr, ld = len(name), len(level), len(guild), len(rank), len(disc_user)
    idx = 0
    if len(lines) > 1:
        for line in lines[1:]:
            columns = line.split("|")
            if len(columns) >= 4:
                char_name, funcom_id = columns[1].strip(), columns[3].strip()
                if char_name == "":
                    continue
                characters = Owner.get_by_name(char_name, include_guilds=False)
                if len(characters) == 1:
                    char = characters[0]
                elif len(characters) > 1:
                    for c in characters:
                        if c.account.funcom_id == funcom_id:
                            char = c
                            break
                else:
                    logger.error(f"Function listplayers couldn't find character named {list[idx]['name']} in db.")
                    continue
                if char.user is None:
                    logger.error(f"Char {char.name} has no user assigned.")
                    continue
                list.append(
                    {
                        "name": char_name,
                        "funcom_id": funcom_id,
                        "guild": char.guild.name if char and char.has_guild else "",
                        "rank": char.rank_name if char and char.has_guild else "",
                        "level": str(char.level) if char else "",
                        "disc_user": char.user.disc_user if char else "",
                    }
                )
                idx = len(list) - 1
                ln = max(ln, len(list[idx]["name"]))
                ll = max(ll, len(list[idx]["level"]))
                lg = max(lg, len(list[idx]["guild"]))
                lr = max(lr, len(list[idx]["rank"]))
                ld = max(ld, len(list[idx]["disc_user"]))
    list.sort(key=lambda user: user["name"])
    for line in list:
        names.append(f"{line['name']:<{ln}} | {line['guild']}")
    num = len(list)
    if num == 0:
        return ("Nobody is currently online", True)
    else:
        nl = "\n"
        headline = f"{name:<{ln}} | {guild}\n"
        width = len(headline) - len(guild) - 1 + lg
        headline = headline + width * "-" + "\n"
        return (f"__**Players online:**__ {len(list)}\n```{headline}{nl.join(names)}```", True)


async def whitelist_player(funcom_id):
    # intercept obvious wrong cases
    if not is_hex(funcom_id) or len(funcom_id) < 14 or len(funcom_id) > 16:
        return (f"{funcom_id} is not a valid FuncomID.", False)
    elif funcom_id == "8187A5834CD94E58":
        return (f"{funcom_id} is the example FuncomID of Midnight.", False)

    # try whitelisting via rcon
    msg = "Whitelisting failed. Server didn't respond. Please try again later."

    # repeat is set to True for the first iteration
    repeat = True
    while repeat:
        # the working assumption is that no repetition is required
        repeat = False
        if exiles_api.trc:
            msg, success = await exiles_api.trc.safe_send_cmd(f"WhitelistPlayer {funcom_id}")
        else:
            return "Server is not running right now, please try again later.", False

        # if whitelisting fails because there was still a previous rcon result cached try again after 1 second
        if not success and msg.startswith('Idx | Char name'):
            repeat = True
            msg = "Whitelisting failed. Server didn't respond. Please try again later."
            await asyncio.sleep(1)

    if not success:
        return msg, success

    if msg == f"Player {funcom_id} added to whitelist.":
        return (msg, True)

    # handle possible failure messages
    # msg is unchanged if server is completely down and doesn't react
    if msg == "Whitelisting failed. Server didn't respond. Please try again later.":
        write2file = True
    # before server has really begun starting up, still allows writing to file
    elif msg == 'Couldn\'t find the command: WhitelistPlayer. Try "help"':
        write2file = True
    # server is up but rejected command
    elif msg == "Still processing previous command.":
        write2file = False
    # unknown? If it ever gets here, take note of msg and see if writing to file is possible
    else:
        write2file = False
        logger.error(f"Unknown RCon error message: {msg}")

    # write funcom_id to file directly
    if write2file and not is_running("ConanSandboxServer"):
        update_whitelist_file(funcom_id)
        msg = f"Player {funcom_id} added to whitelist."
    # try again later
    elif write2file:
        msg = "Server is not ready. Please try again later."
    return (msg, True)


async def unwhitelist_player(funcom_id):
    msg = "Unwhitelisting failed. Server didn't respond. Please try again later."

    if exiles_api.trc:
        msg, success = await exiles_api.trc.safe_send_cmd(f"UnwhitelistPlayer {funcom_id}")
    else:
        return "Server is not running right now, please try again later.", False

    if not success:
        return msg, success

    if msg == f"Player {funcom_id} removed from whitelist.":
        return (msg, True)

    # handle possible failure messages
    # when server is completely down and doesn't react
    if msg == "Unwhitelisting failed. Server didn't respond. Please try again later.":
        write2file = True
    # before server has really begun starting up, still allows writing to file
    elif msg == 'Couldn\'t find the command: UnWhitelistPlayer. Try "help"':
        write2file = True
    # server is up but rejected command
    elif msg == "Still processing previous command.":
        write2file = False
    # unknown? If it ever gets here, take note of msg and see if writing to file is possible
    else:
        write2file = False
        logger.error(f"Unknown RCon error message: {msg}")

    # remove funcom_id from file directly
    if write2file and not is_running("ConanSandboxServer"):
        update_whitelist_file(funcom_id, add=False)
        msg = f"Player {funcom_id} removed from whitelist."
    # try again later
    elif write2file and is_running("ConanSandboxServer"):
        msg = "Server is not ready. Please try again later."
    return (msg, True)


async def get_time() -> tuple:
    if exiles_api.trc:
        return await exiles_api.trc.safe_send_cmd("TERPO getTime")
    else:
        return "Server is not running right now, please try again later.", False


async def set_time(time) -> tuple:
    if exiles_api.trc:
        return await exiles_api.trc.safe_send_cmd(f"TERPO setTime {time}")
    else:
        return "Server is not running right now, please try again later.", False


async def get_time_decimal():
    logger.info("Trying to read the time from the game server.")
    if exiles_api.trc:
        result, success = await exiles_api.trc.safe_send_cmd("TERPO getTimeDecimal")
    else:
        success = False
        result = "Server is not running right now, please try again later."
    if not exiles_api.trc or not success:
        logger.error(f"Failed to read time from game server. RConError: {result}")
        return 1
    if not is_float(result):
        logger.info(f"Failed reading time. {result}")
        return 2
    logger.info(f"Time read successfully: {result}")
    GlobalVars.set_value("LAST_RESTART_TIME", result)
    return 0


async def set_time_decimal():
    time = GlobalVars.get_value("LAST_RESTART_TIME")
    logger.info(f"Trying to reset the time to the previously read time of {time}")
    if exiles_api.trc:
        result, success = await exiles_api.trc.safe_send_cmd(f"TERPO setTimeDecimal {time}")
    else:
        success = False
        result = "Server is not running right now, please try again later."
    if not exiles_api.trc or not success:
        logger.error(f"Failed to set time {time}. RConError: err == {result}")
        return 1
    if not result.startswith("Time has been set to"):
        logger.info(f"Failed setting time. {result}")
        return 2
    logger.info("Time was reset successfully!")
    return 0

async def split_message(message, length=2000, separator='\n'):
        length = length - len(separator)
        chunk = ""
        chunks = []
        lines = message.split(separator)
        for line in lines:
                if len(chunk) > 0 and (len(chunk) + len(line)) >= length:
                    chunks.append(chunk)
                    chunk = ''
                chunk += (separator + line)

        if len(chunk) > 0:
            chunks.append(chunk)
        return chunks

# errors in tasks raise silently normally so lets make them speak up
def exception_catching_callback(task):
    if task.exception():
        logger.error("Error in task.")
        task.print_stack()
