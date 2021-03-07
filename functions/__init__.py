import discord, re, pprint
from discord import Member
from discord.ext import commands
from datetime import timedelta, datetime
from factorio_rcon import RCONClient
from psutil import process_iter
from logger import logger
from config import *
from exiles_api import *

rcon = RCONClient(RCON_IP, RCON_PORT, RCON_PASSWORD, timeout=5.0, connect_on_init=False)

def pp(arg):
    printer = pprint.PrettyPrinter(indent=4)
    printer.pprint(arg)

def pe(arg):
    print(f"error: {arg}")
    print(f" type: {type(arg)}")
    print( "  dir: ")
    pp(dir(arg))

def get_guild(bot=None, guild=None):
    if guild:
        return guild
    elif bot:
        return discord.utils.get(bot.guilds, name=DISCORD_NAME)
    else:
        logger.error('Called get_guild() but passed neither bot nor guild.')
        return None

def get_categories(guild=None, bot=None):
    guild = get_guild(bot, guild)
    if guild:
        return {category.name: category for category in guild.categories}
    return None

def get_channels(guild=None, bot=None):
    guild = get_guild(bot, guild)
    if guild:
        return {channel.name: channel for channel in guild.channels}
    logger.error('Called get_channels() but passed neither bot nor guild.')
    return None

def get_roles(guild=None, bot=None):
    guild = get_guild(bot, guild)
    if guild:
        return {role.name: role for role in guild.roles}
    logger.error('Called get_roles() but passed neither bot nor guild.')
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

def parse(guild, user, msg):
    channels = get_channels(guild)
    roles = get_roles(guild)
    msg = str(msg).replace('{PREFIX}', PREFIX) \
                  .replace('{OWNER}', guild.owner.mention)
    msg = msg.replace('{PLAYER}', user.mention) if type(user) is Member else msg.replace('{PLAYER}', str(user))
    for name, channel in channels.items():
        msg = re.sub("(?i){" + name + "}", channel.mention, msg)
    for name, role in roles.items():
        msg = re.sub("(?i){" + name + "}", role.mention, msg)
    return msg

def is_hex(s):
    return all(c in '1234567890ABCDEF' for c in s.upper())

def is_float(s):
    return re.match(r'^-?\d+(?:\.\d+)?$', s) is not None

def rreplace(s, old, new):
    li = s.rsplit(old, 1)
    return new.join(li)

def listplayers():
    try:
        rcon.connect()
        rcon.send_packet(0, 2, 'ListPlayers')
        packets = rcon.receive_packets()
        rcon.close()
        result = packets[0].body
    except Exception as err:
        return (str(err), False)
    lines = result.split('\n')
    list, names = [], []
    name, level, guild, rank, disc_user = 'Char name', 'Level', 'Clan name', 'Rank', 'Discord'
    ln, ll, lg, lr, ld = len(name), len(level), len(guild), len(rank), len(disc_user)
    idx = 0
    if len(lines) > 1:
        for line in lines[1:]:
            columns = line.split('|')
            if len(columns) >= 4:
                char_name, funcom_id = columns[1].strip(), columns[3].strip()
                if char_name == '':
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
                list.append({'name': char_name,
                             'funcom_id': funcom_id,
                             'guild': char.guild.name if char and char.has_guild else '',
                             'rank': char.rank_name if char and char.has_guild else '',
                             'level': str(char.level) if char else '',
                             'disc_user': char.user.disc_user if char else ''})
                idx = len(list) - 1
                ln = max(ln, len(list[idx]['name']))
                ll = max(ll, len(list[idx]['level']))
                lg = max(lg, len(list[idx]['guild']))
                lr = max(lr, len(list[idx]['rank']))
                ld = max(ld, len(list[idx]['disc_user']))
    list.sort(key=lambda user: user['name'])
    for line in list:
        names.append(f"{line['name']:<{ln}} | {line['guild']}")
    num = len(list)
    if num == 0:
        return ("Nobody is currently online", True)
    else:
        nl = '\n'
        headline = f"{name:<{ln}} | {guild}\n"
        width = len(headline) - len(guild) - 1 + lg
        headline = headline + width * '-' + '\n'
        return (f"__**Players online:**__ {len(list)}\n```{headline}{nl.join(names)}```", True)

def is_time_format(time):
    tLst = time.split(':')
    if not tLst:
        return False

    if len(tLst) >= 1 and tLst[0].isnumeric() and int(tLst[0]) >= 0:
        hours = str(int(tLst[0]) % 24)
    else:
        return False

    if len(tLst) >= 2 and tLst[1].isnumeric() and int(tLst[1]) >= 0 and int(tLst[1]) < 60:
        minutes = tLst[1]
    elif len(tLst) < 2:
        minutes = '00'
    else:
        return False

    if len(tLst) >= 3 and tLst[2].isnumeric() and int(tLst[2]) >= 0 and int(tLst[2]) < 60:
        seconds = tLst[2]
    elif len(tLst) < 3:
        seconds = '00'
    else:
        return False

    return ':'.join([hours, minutes, seconds])

def get_time():
    try:
        rcon.connect()
        rcon.send_packet(0, 2, "TERPO getTime")
        packets = rcon.receive_packets()
        rcon.close()
        result = packets[0].body
    except Exception as err:
        return (str(err), False)
    return (result, True)

def set_time(time):
    try:
        rcon.connect()
        rcon.send_packet(0, 2, f"TERPO setTime {time}")
        packets = rcon.receive_packets()
        rcon.close()
        result = packets[0].body
    except Exception as err:
        return (str(err), False)
    return (result, True)

def get_time_decimal():
    logger.info(f"Trying to read the time from the game server.")
    try:
        rcon.connect()
        rcon.send_packet(0, 2, f"TERPO getTimeDecimal")
        packets = rcon.receive_packets()
        rcon.close()
        result = packets[0].body
    except Exception as err:
        logger.error(f"Failed to read time from game server. RConError: {str(err)}")
        return 1
    if not is_float(result):
        logger.info(f"Failed reading time. {time}")
        return 2
    logger.info(f"Time read successfully: {result}")
    GlobalVars.set_value('LAST_RESTART_TIME', result)
    return 0

def set_time_decimal():
    time = GlobalVars.get_value('LAST_RESTART_TIME')
    logger.info(f"Trying to reset the time to the previously read time of {time}")
    try:
        rcon.connect()
        rcon.send_packet(0, 2, f"TERPO setTimeDecimal {time}")
        packets = rcon.receive_packets()
        rcon.close()
        result = packets[0].body
    except Exception as err:
        logger.error(f"Failed to set time {time}. RConError: err == {str(err)}")
        return 1
    if not result.startswith("Time has been set to"):
        logger.info(f"Failed setting time. {result}")
        return 2
    logger.info("Time was reset successfully!")
    return 0

def is_running(process_name, strict=False):
    '''Check if there is any running process that contains the given name process_name.'''
    #Iterate over the all the running process
    for proc in process_iter():
        try:
            # Check if process name contains the given name string.
            if process_name.lower() in proc.name().lower():
                return True
        except:
            pass
    return False

def is_on_whitelist(funcom_id):
    try:
        with open(WHITELIST_PATH, 'rb') as f:
            line = f.readline()
            codec = 'utf16' if line.startswith(b'\xFF\xFE') else 'utf8'
    except:
        return False
    try:
        with open(WHITELIST_PATH, 'r', encoding=codec) as f:
            lines = f.readlines()
    except:
        return False
    funcom_id = funcom_id.upper()
    for line in lines:
        if funcom_id in line.upper():
            return True
    return False

def whitelist_player(funcom_id):
    # intercept obvious wrong cases
    if not is_hex(funcom_id) or len(funcom_id) < 14 or len(funcom_id) > 16:
        return (f"{funcom_id} is not a valid FuncomID.", False)
    elif funcom_id == "8187A5834CD94E58":
        return (f"{funcom_id} is the example FuncomID of Midnight.", False)

    # try whitelisting via rcon
    msg = "Whitelisting failed. Server didn't respond. Please try again later."
    try:
        rcon.connect()
        rcon.send_packet(0, 2, f"WhitelistPlayer {funcom_id}")
        packets = rcon.receive_packets()
        rcon.close()
        msg = packets[0].body
    except Exception as err:
        return (str(err), False)

    if msg == f"Player {funcom_id} added to whitelist.":
        return (msg, True)

    # handle possible failure messages
    # msg is unchanged if server is completely down and doesn't react
    if msg == "Whitelisting failed. Server didn't respond. Please try again later.":
        write2file = True
    # before server has really begun starting up, still allows writing to file
    elif  msg == "Couldn't find the command: WhitelistPlayer. Try \"help\"":
        write2file = True
    # server is up but rejected command
    elif msg == "Still processing previous command.":
        write2file = False
    # unknown? If it ever gets here, take note of msg and see if writing to file is possible
    else:
        write2file = False
        logger.error(f"Unknown RCon error message: {msg}")

    # write funcom_id to file directly
    if write2file and not is_running('ConanSandboxServer'):
        update_whitelist_file(funcom_id)
        msg = f"Player {funcom_id} added to whitelist."
    # try again later
    elif write2file:
        msg = f"Server is not ready. Please try again later."
    return (msg, True)

def unwhitelist_player(funcom_id):
    msg = "Unwhitelisting failed. Server didn't respond. Please try again later."
    try:
        rcon.connect()
        rcon.send_packet(0, 2, f"UnWhitelistPlayer {funcom_id}")
        packets = rcon.receive_packets()
        rcon.close()
        msg = packets[0].body
    except Exception as err:
        return (str(err), False)

    if msg == f"Player {funcom_id} removed from whitelist.":
        return (msg, True)

    # handle possible failure messages
    # when server is completely down and doesn't react
    if msg == "Unwhitelisting failed. Server didn't respond. Please try again later.":
        write2file = True
    # before server has really begun starting up, still allows writing to file
    elif  msg == "Couldn't find the command: UnWhitelistPlayer. Try \"help\"":
        write2file = True
    # server is up but rejected command
    elif msg == "Still processing previous command.":
        write2file = False
    # unknown? If it ever gets here, take note of msg and see if writing to file is possible
    else:
        write2file = False
        logger.error(f"Unknown RCon error message: {msg}")

    # remove funcom_id from file directly
    if write2file and not is_running('ConanSandboxServer'):
        update_whitelist_file(funcom_id, add=False)
        msg = f"Player {funcom_id} removed from whitelist."
    # try again later
    elif write2file and is_running('ConanSandboxServer'):
        msg = f"Server is not ready. Please try again later."
    return (msg, True)

def update_whitelist_file(funcom_id, add=True):
    is_on_whitelist = is_on_whitelist(funcom_id)
    if (is_on_whitelist and add) or (not is_on_whitelist and not add):
        return
    # determine codec
    try:
        with open(WHITELIST_PATH, 'rb') as f:
            line = f.readline()
            codec = 'utf16' if line.startswith(b'\xFF\xFE') else 'utf8'
    except:
        codec = 'utf8'
    try:
        with open(WHITELIST_PATH, 'r', encoding=codec) as f:
            lines = f.readlines()
    except:
        with open(WHITELIST_PATH, 'w') as f:
            pass
        lines = []
    # removed duplicates and lines with INVALID. Ensure that each line ends with a newline character
    filtered = set()
    names = {}
    # define regular expression to filter out unprintable characters
    control_chars = ''.join(map(chr, itertools.chain(range(0x00,0x20), range(0x7f,0xa0))))
    control_char_re = re.compile('[%s]' % re.escape(control_chars))
    for line in lines:
        if line != "\n" and not "INVALID" in line and (add or not funcom_id in line):
            # remove unprintable characters from the line
            res = control_char_re.sub('', line)
            res = res.split(':')
            id = res[0].strip()
            if len(res) > 1:
                name = res[1].strip()
            else:
                name = 'Unknown'
            filtered.add(id)
            if not id in names or names[id] == 'Unknown':
                names[id] = name
    if add:
        filtered.add(funcom_id)
    names[funcom_id] = 'Unknown'
    wlist = []
    for id in filtered:
        wlist.append(id + ':' + names[id] + '\n')
    wlist.sort()
    with open(WHITELIST_PATH, 'w') as f:
        f.writelines(wlist)

async def get_member(ctx, name):
    if not name is str:
        name = str(name)
    try:
        return await commands.MemberConverter().convert(ctx, name)
    except:
        try:
            return await commands.MemberConverter().convert(ctx, name.capitalize())
        except:
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
        if len(messages[-1] + "\n" + chunk) <= 2000:
            chunk = messages[-1] + "\n" + chunk
            msgs = messages[:-1]
    fmt = '%A %d-%b-%Y UTC'
    freq = category.frequency
    now = datetime.utcnow()
    for group in groups:
        # owner doesn't exist anymore
        if group.name is None:
            if len(group.owners) > 0:
                owner = group.owners[0]
                name = session.query(OwnersCache.name).filter_by(id=group.owner.id).scalar()
                line = f"**{name}: Not found in db and may have to be deleted."
            continue
        elif group.name == 'Ruins':
            owner = group.owners[0]
            name = session.query(OwnersCache.name).filter_by(id=owner.id).scalar() + ' (Ruins)'
        else:
            name = group.name
        last_pay = group.last_payment.strftime(fmt) if group.last_payment else 'Never'
        next_due = group.next_due if last_pay == 'Never' else group.last_payment + freq
        line = f"**{name}:**\nLast payment: {last_pay}.\nNext due: {next_due.strftime(fmt)}"
        line += ". **(Overdue)**\n\n" if now > next_due else "\n\n"

        if len(chunk + line) > 2000:
            msgs.append(chunk)
            chunk = line
        else:
            chunk += line
    msgs.append(chunk)
    return msgs

async def get_category_msg_original(category, messages=[]):
    groups = [g for g in session.query(Groups).filter_by(category=category).all()]
    if len(groups) == 0:
        return messages
    groups.sort(key=lambda owner: owner.name)
    type = "Clans" if category.guild_pay else "Characters"
    chunk = f"__**{type}** and groups in category **{category.cmd}**:__\n"
    msgs = []
    if len(messages) > 0:
        if len(messages[-1] + "\n" + chunk) <= 2000:
            chunk = messages[-1] + "\n" + chunk
            msgs = messages[:-1]
    for group in groups:
        last_pay = group.last_payment.strftime('%A %d-%b-%Y %H:%M UTC') if group.last_payment else 'Never'
        next_due = group.next_due.strftime('%A %d-%b-%Y %H:%M UTC')
        if category.frequency == timedelta(weeks=1):
            dur = 'week'
        elif category.frequency == timedelta(days=28):
            dur = 'month'
        else:
            dur = 'billing period'
        if group.balance > 0:
            line = (f"**{group.name}** has **already paid for this {dur}**. "
                    f"Last payment was made: **{last_pay}**.\n")
        elif group.balance == 0:
            line = (f"**{group.name}** has **not paid for this {dur} yet**. "
                    f"Last payment was made: **{last_pay}**. "
                    f"Next payment is due on **{next_due}** at the latest.\n")
        else:
            periods = f" ({abs(group.balance)} billing periods)" if group.balance < -1 else ''
            line = (f"**{group.name}'s** payment is **overdue{periods}**. Last payment was made: **{last_pay}**.\n")
        if len(chunk + line) > 2000:
            msgs.append(chunk)
            chunk = line
        else:
            chunk += line
    msgs.append(chunk)
    return msgs

async def get_category_msg_compact(category, messages=[]):
    groups = [g for g in session.query(Groups).filter_by(category=category).all()]
    if len(groups) == 0:
        return messages
    groups.sort(key=lambda owner: owner.name)
    type = "Clans" if category.guild_pay else "Characters"
    list, lines = [], []
    name_hl, next_due_hl, last_payment_hl = 'Name', 'Next due date (UTC)', 'Last payment (UTC)'
    ln, lnd, llp = len(name_hl), len(next_due_hl), len(last_payment_hl)
    date_format = '%A %d-%b-%Y %H:%M'
    if category.frequency == timedelta(weeks=1):
        dur = 'week'
    elif category.frequency == timedelta(days=28):
        dur = 'month'
    else:
        dur = 'billing period'
    for group in groups:
        if group.balance > 0:
            next_due = f"Paid for this {dur}"
        elif group.balance == 0:
            next_due = group.last_payment.strftime(date_format)
        else:
            next_due = ">> OVERDUE! <<"
        last_payment = group.last_payment.strftime(date_format) if group.last_payment else 'Never'
        list.append({'name': group.name, 'last_pay': last_payment, 'next_due': next_due})
        ln = max(ln, len(group.name))
        lnd = max(lnd, len(next_due))
        llp = max(llp, len(last_payment))
    list.sort(key=lambda user: user['name'])
    for line in list:
        lines.append(f"{line['name']:<{ln}} | {line['next_due']:<{lnd}} | {line['last_pay']}")
    nl = '\n'
    headline = f"{name_hl:<{ln}} | {next_due_hl:<{lnd}} | {last_payment_hl}\n"
    width = len(headline) - len(last_payment_hl) - 1 + llp
    headline = headline + width * '-'
    chunk = f"__**{type}** and groups in category **{category.cmd}**:__\n```{headline}"
    msgs = []
    for line in lines:
        if len(chunk + "\n" + line + "```") <= 2000:
            chunk = chunk + "\n" + line
        else:
            msgs.append(chunk + "```")
            chunk = "```" + line
    msgs.append(chunk + "```")
    return messages + msgs

async def get_user_msg(groups, messages=[]):
    chunk, msgs = "", []
    if len(messages) > 0:
        if len(messages[-1] + chunk) <= 2000:
            chunk = messages[-1] + chunk
            msgs = messages[:-1]
    fmt = '%A %d-%b-%Y UTC'
    now = datetime.utcnow()
    for group in groups:
        freq = group.category.frequency
        last_pay = group.last_payment.strftime(fmt) if group.last_payment else 'Never'
        next_due = group.next_due if last_pay == 'Never' else group.last_payment + freq
        line = f"**{group.name}** last paid their **{group.category.name}** on **{last_pay}**.\n"
        if now < next_due:
            line += f"Next payment is due on **{next_due.strftime(fmt)}**.\n"
        else:
            line += f"Next payment **was** due on **{next_due.strftime(fmt)}**. **(Overdue)**\n"
        if len(chunk + line) > 2000:
            msgs.append(chunk)
            chunk = line
        else:
            chunk += line
    if chunk != '':
        msgs.append(chunk)
    return msgs

async def payments(id, category_id):
    while True:
        messaged = False
        # quit task if group has been deleted
        group = session.query(Groups).get(id)
        if not group:
            name = session.query(OwnersCache.name).filter_by(id=id).scalar()
            guess = '(' + name + ') ' if name else ''
            logger.info(f"Group with id {id} {guess}no longer exists. Task has not been renewed.")
            break
        # remove characters and clans from groups if they no longer exist
        for cat_owner in group.owners:
            if not Owner.get(cat_owner.id):
                name = session.query(OwnersCache.name).filter_by(id=cat_owner.id).scalar()
                guess = '(' + name + ') ' if name else ''
                logger.info(f"Character or clan with id {id} {guess}and category_id {category_id} removed "
                             "from payments list because they have been deleted from db since last time.")
                messaged = True
                session.delete(cat_owner)
        # remove simple groups that are empty
        if (group.is_simple and messaged and len(group.owners) <= 1) or (not messaged and len(group.owners) == 0):
            if not messaged:
                logger.info(f"Character or clan with id {id} and category_id {category_id} removed "
                             "from payments list because they have been deleted from db since last time.")
            session.delete(group)
        await discord.utils.sleep_until(group.next_due)
        group.next_due = group.next_due + group.category.frequency
        group.balance -= 1
        logger.info(f"Deducted 1 bpp from {group.name} ({id}). New balance is {group.balance}. "
                    f"Next due date has been set to {group.next_due.strftime('%A %d-%b-%Y %H:%M UTC')}.")
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
            logger.info(f"Category with id {id} removed from payments list "
                         "because they have been deleted from db since last time.")
            break
        if cat.verbosity == 0:
            break
        if cat.frequency > timedelta(days=1):
            delay = timedelta(days=1) + timedelta(seconds=cat.id*5)
        elif cat.frequency >= timedelta(days=1):
            delay = timedelta(hours=12) + timedelta(seconds=cat.id*5)
        elif cat.frequency >= timedelta(hours=1):
            delay = timedelta(minutes=30) + timedelta(seconds=cat.id*5)
        else:
            break

        next_due = next_time(cat.start) - delay if not next_due else next_due + cat.frequency
        if next_due <= datetime.utcnow():
            next_due += cat.frequency
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
            if guild.name in message.content:
                found = True
                group.balance += 1
                group.last_payment = datetime.utcnow()
                logger.info(f"Added 1 bpp to {group.name} ({group.id}).")
            else:
                for char in guild.members:
                    if char.name in message.content:
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
            group = cat_owner.group
            if char.name in message.content:
                found = True
                group.balance += 1
                group.last_payment = datetime.utcnow()
                logger.info(f"Added 1 bpp to {group.name} ({group.id}).")
    session.commit()

# errors in tasks raise silently normally so lets make them speak up
def exception_catching_callback(task):
    if task.exception():
        logger.error("Error in task.")
        task.print_stack()
