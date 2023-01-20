import asyncio
import re
import itertools
from discord.ext import commands
from discord.ext.commands import command
from logger import logger
from checks import has_role_greater_or_equal, has_role
from config import SUPPORT_ROLE, ADMIN_ROLE, WHITELIST_PATH
from exiles_api import session, is_running, Users
from functions import (
    listplayers, get_member, whitelist_player, unwhitelist_player,
    get_time, set_time, is_on_whitelist, is_time_format, split_message
)
from cogs.applications import Applications


class RCon(commands.Cog, name="RCon commands"):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def update_user(funcom_id, member):
        removed = []
        # get all users who share either of the three attributes
        users = (
            session.query(Users)
            .filter((Users.disc_id == member.id) | (Users.disc_user == str(member)) | (Users.funcom_id == funcom_id))
            .all()
        )
        # if none were found, create a new user
        if len(users) == 0:
            new_user = Users(disc_user=str(member), disc_id=member.id, funcom_id=funcom_id)
            session.add(new_user)
        # if only one was found, update that user
        elif len(users) == 1:
            user = users[0]
            if user.funcom_id and user.funcom_id != funcom_id:
                removed = [user.funcom_id]
            user.disc_id = member.id
            user.disc_user = str(member)
            user.funcom_id = funcom_id
        # if more than one were found, either consolidate or deny
        else:
            # desired funcom_id is already used by another user => deny
            user = session.query(Users).filter_by(funcom_id=funcom_id).first()
            if user:
                return False
            # disc_user and disc_id are in two separate rows => consolidate
            user = session.query(Users).filter_by(disc_user=str(member)).first()
            if user.funcom_id:
                removed = [user.funcom_id]
            session.delete(user)
            user = session.query(Users).filter_by(disc_id=member.id).first()
            if user.funcom_id:
                removed += [user.funcom_id]
            user.disc_user = str(member)
            user.funcom_id = funcom_id
        session.commit()
        return removed if len(removed) > 0 else True

    @staticmethod
    async def remove_user(funcom_id):
        # get the user with the given funcom_id
        user = session.query(Users).filter_by(funcom_id=funcom_id).first()
        # if none were found, return false
        if user:
            session.delete(user)
            session.commit()
        # if only one was found, update that user
        else:
            return False

    @command(
        name="listplayers",
        aliases=["playerslist", "playerlist", "listplayer"],
        help="Shows a list of all players online right now",
    )
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def listplayers(self, ctx):
        playerlist, _ = await asyncio.create_task(listplayers())
        chunks = await split_message(playerlist)
        sep = ''
        for chunk in chunks:
            msg = sep + chunk + '```'
            await ctx.send(msg)
            sep = '```'
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="whitelist", aliases=["whitelistplayer"], help="Whitelists the player using the given FuncomID")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whitelist(self, ctx, *, Arguments):
        funcom_id = await Applications.get_funcom_id_in_text(Arguments, upper_case=False)
        if not funcom_id:
            msg = (
                "No valid FuncomID given. ID needs to be 14-16 characters "
                "long and consist only of digits and letters A-F."
            )
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return

        arg_list = Arguments.split()
        arg_list.remove(funcom_id)
        funcom_id = funcom_id.upper()

        member = await get_member(ctx, " ".join(arg_list))
        if not member:
            msg = f"Couldn't get id for {' '.join(arg_list)}. Are you sure they are still on this discord server?"
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        success = await self.update_user(funcom_id, member)
        if not success:
            msg = "Failed to whitelist. FuncomID already in use by another player."
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        removed = None
        if isinstance(success, list):
            removed = success
            for id in removed:
                result, _ = unwhitelist_player(id)
                if not result.endswith("removed from whitelist."):
                    await ctx.send(
                        f"Unwhitelisting former FuncomID {id} failed. Server didn't respond. Please try again later."
                    )
        msg, _ = await whitelist_player(funcom_id)
        if removed:
            r = (
                "FuncomID " + removed[0] + " was"
                if len(removed) == 1
                else "FuncomIDs " + removed[0] + " and " + removed[1] + " were"
            )
            msg += f" Previous {r} removed from whitelist."
        await ctx.send(msg)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")

    @command(name="unwhitelist", help="Unwhitelists the player using the given FuncomID")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def unwhitelist(self, ctx, *, FuncomID):
        funcom_id = await Applications.get_funcom_id_in_text(FuncomID)
        if not funcom_id:
            msg = (
                "No valid FuncomID given. ID needs to be 14-16 characters "
                "long and consist only of digits and letters A-F."
            )
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        elif not is_on_whitelist(funcom_id):
            msg = f"FuncomID {funcom_id} is not on the whitelist."
            await self.remove_user(funcom_id)
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        await self.remove_user(funcom_id)
        result, _ = await unwhitelist_player(funcom_id)
        if not result.endswith("removed from whitelist."):
            msg = f"Unwhitelisting FuncomID {funcom_id} failed. Please try again later."
        else:
            msg = result
        await ctx.send(msg)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")

    @command(
        name="whitelistall",
        help="Whitelists everyone who's currently in the supplemental database. " "Only works while server is down.",
    )
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whitelistall(self, ctx):
        if is_running("ConanSandboxServer"):
            await ctx.send("Command can only be used while server isn't running.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
            return
        # determine codec
        try:
            with open(WHITELIST_PATH, "rb") as f:
                line = f.readline()
                codec = "utf16" if line.startswith(b"\xFF\xFE") else "utf8"
        except BaseException:
            codec = "utf8"
        # try to read all entries already in the whitelist.txt file
        try:
            with open(WHITELIST_PATH, "r", encoding=codec) as f:
                lines = f.readlines()
        # if file doesn't exist create an empty list
        except BaseException:
            with open(WHITELIST_PATH, "w") as f:
                pass
            lines = []

        # split lines into id and name. Remove duplicates.
        filtered = set()
        names = {}
        # define regular expression to filter out unprintable characters
        control_chars = "".join(map(chr, itertools.chain(range(0x00, 0x20), range(0x7F, 0xA0))))
        control_char_re = re.compile("[%s]" % re.escape(control_chars))
        for line in lines:
            if line != "\n" and "INVALID" not in line:
                # remove unprintable characters from the line
                res = control_char_re.sub("", line)
                res = res.split(":")
                id = res[0].strip()
                if len(res) > 1:
                    name = res[1].strip()
                else:
                    name = "Unknown"
                filtered.add(id)
                # if duplicate values exist, prioritize those containing a funcom_name
                if id not in names or names[id] == "Unknown":
                    names[id] = name

        # go through the Users table and supplement missing users if any
        for user in session.query(Users).all():
            if user.funcom_id not in filtered:
                filtered.add(user.funcom_id)
                names[user.funcom_id] = "Unknown"

        # create lines to write into new whitelist.txt
        wlist = []
        for id in filtered:
            wlist.append(id + ":" + names[id] + "\n")
        wlist.sort()

        # overwrite / write the new file with the contenst of wlist
        with open(WHITELIST_PATH, "w", encoding=codec) as f:
            f.writelines(wlist)
        await ctx.send("All players in the supplemental database have been placed on the whitelist.")

    @command(name="gettime", help="Tells the current time on the server")
    async def gettime(self, ctx):
        anc = f"Author: {ctx.author} / Command: {ctx.message.content}."
        result, success = await get_time()
        failed = "RCon error. Failed to get time. Try again in a few seconds."
        if success and is_time_format(result):
            msg = f"It's currently **{result}** on the server."
            logger.info(f"{anc} Current server time was sent to {ctx.author}.")
        elif result:
            msg = failed
            logger.error(f"{anc} RConError: {result}")
        else:
            msg = failed
            logger.error(f"{anc} Error.")
        await ctx.send(msg)

    @command(name="settime", help="Sets the time on the server")
    @has_role(ADMIN_ROLE)
    async def settime(self, ctx, Time):
        anc = f"Author: {ctx.author} / Command: {ctx.message.content}."
        time = is_time_format(Time)
        if not time:
            msg = "Bad time format. Please enter time in HH[:MM[:SS]] 24h format."
        else:
            result, success = await set_time(time)
            failed = "RCon error. Failed to set time. Try again later."
            if success and result.startswith("Time has been set to"):
                msg = result
                logger.info(f"{anc} Current server time was set to {time} by {ctx.author}.")
            elif result:
                msg = failed
                logger.error(f"{anc} RConError: {result}")
            else:
                msg = failed
                logger.error(f"{anc} Error.")
        await ctx.send(msg)


def setup(bot):
    bot.add_cog(RCon(bot))
