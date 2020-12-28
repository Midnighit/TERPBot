import discord, re
from datetime import timedelta, datetime
from logger import logger
from discord import Member
from discord.ext import commands
from config import *
from exiles_api import *

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

async def get_member(ctx, name):
    try:
        return await commands.MemberConverter().convert(ctx, name)
    except:
        try:
            return await commands.MemberConverter().convert(ctx, name.capitalize())
        except:
            return None

async def get_category_msg(category, messages=[]):
    owners = [o for o in session.query(CatUsers).filter_by(category_id=category.id).order_by(CatUsers.name).all()]
    if len(owners) == 0:
        return messages
    type = "Clans" if category.guild_pay else "Characters"
    chunk = f"__**{type}** in category **{category.cmd}**:__\n"
    msgs = []
    if len(messages) > 0:
        if len(messages[-1] + "\n" + chunk) <= 2000:
            chunk = messages[-1] + "\n" + chunk
            msgs = messages[:-1]
    for owner in owners:
        last_pay = owner.last_payment.strftime('%A %d-%b-%Y %H:%M UTC') if owner.last_payment else 'Never'
        if owner.balance >= 0:
            line = f"**{owner.name}** currently has **no open bill**. Last payment was made: **{last_pay}**.\n"
        else:
            period = "period" if abs(owner.balance) == 1 else "periods"
            line = (f"**{owner.name}** currently owes **{abs(owner.balance)} billing {period}**. "
                    f"Last payment was made: **{last_pay}**.\n")
        if len(chunk + line) > 2000:
            msgs.append(chunk)
            chunk = line
        else:
            chunk += line
    msgs.append(chunk)
    return msgs

async def get_user_msg(cat_users, messages=[]):
    chunk, msgs = "", []
    if len(messages) > 0:
        if len(messages[-1] + chunk) <= 2000:
            chunk = messages[-1] + chunk
            msgs = messages[:-1]
    for owner in cat_users:
        last_pay = owner.last_payment.strftime('%A %d-%b-%Y %H:%M UTC') if owner.last_payment else 'Never'
        if owner.balance >= 0:
            line = (f"**{owner.name}** currently **has no open bill** for **{owner.category.name}**. "
                    f"Last payment was made: **{last_pay}**.\n")
        else:
            period = "period" if abs(owner.balance) == 1 else "periods"
            line = (f"**{owner.name}** owes **{abs(owner.balance)} billing {period}** fee for their "
                    f"**{owner.category.name}**. Last payment was made: **{last_pay}**.\n")
        if len(chunk + line) > 2000:
            msgs.append(chunk)
            chunk = line
        else:
            chunk += line
    msgs.append(chunk)
    return msgs

async def payments(id, category_id):
    while True:
        # confirm that user still exists otherwise break
        cat_user = session.query(CatUsers).filter_by(id=id, category_id=category_id).first()
        if not cat_user:
            logger.info(f"User with id {id} and category_id {category_id} removed from payments list "
                         "because they have been deleted from db since last time.")
            break
        await discord.utils.sleep_until(cat_user.next_due)
        cat_user.next_due = cat_user.next_due + cat_user.category.frequency
        cat_user.balance -= 1
        logger.info(f"Deducted 1 bpp from {cat_user.name} ({id}). New balance is {cat_user.balance}. "
                    f"Next due date has been set to {cat_user.next_due.strftime('%A %d-%b-%Y %H:%M UTC')}.")
        session.commit()

async def print_payments_msg(ctx, messages):
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
            delay = timedelta(days=1)
        elif cat.frequency >= timedelta(days=1):
            delay = timedelta(hours=12)
        elif cat.frequency >= timedelta(hours=1):
            delay = timedelta(minutes=30)
        else:
            break

        next_due = CatUsers._next_due(cat.start) - delay if not next_due else next_due + cat.frequency
        if next_due <= datetime.utcnow():
            next_due += cat.frequency
        await discord.utils.sleep_until(next_due)
        for guild in guilds:
            for channel in guild.channels:
                if channel.id == int(cat.output_channel):
                    messages = await get_category_msg(cat)
                    await print_payments_msg(channel, messages)

async def payments_input(category, message):
    cat_users, cat_user_ids, found = {}, [], False
    for cat_user in session.query(CatUsers).filter_by(category_id=category.id).all():
        cat_user_ids.append(cat_user.id)
        cat_users[cat_user.id] = cat_user
    if category.guild_pay:
        for guild in session.query(Guilds).filter(Guilds.id.in_(cat_user_ids)).all():
            cat_user = cat_users[guild.id]
            if cat_user.name != guild.name:
                cat_user.name = guild.name
            if not found and guild.name in message.content:
                found = True
                cat_user.balance += 1
                cat_user.last_payment = datetime.utcnow()
                logger.info(f"Added 1 bpp to {cat_user.name} ({cat_user.id}).")
            elif not found:
                for char in guild.members:
                    if char.name in message.content:
                        found = True
                        cat_user.balance += 1
                        cat_user.last_payment = datetime.utcnow()
                        logger.info(f"Added 1 bpp to {cat_user.name} ({cat_user.id}).")
    else:
        for char in session.query(Characters).filter(Characters.id.in_(cat_user_ids)).all():
            cat_user = cat_users[char.id]
            if cat_user.name != char.name:
                cat_user.name = char.name
            if not found and char.name in message.content:
                found = True
                cat_user.balance += 1
                cat_user.last_payment = datetime.utcnow()
                logger.info(f"Added 1 bpp to {cat_user.name} ({cat_user.id}).")
    session.commit()

# errors in tasks raise silently normally so lets make them speak up
def exception_catching_callback(task):
    if task.exception():
        logger.error("Error in task.")
        task.print_stack()
