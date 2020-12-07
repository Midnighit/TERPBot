import sys, re, itertools, discord
from discord import Member
from discord.ext import commands
from discord.ext.commands import command
from threading import Timer
from datetime import timedelta
from psutil import process_iter
from mcrcon import MCRcon
from config import *
from exiles_api import *
from logger import logger
from exceptions import *
from checks import *
from cogs.general import General
from cogs.applications import Applications

class RCon(commands.Cog, name="RCon commands"):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def is_hex(s):
        return all(c in '1234567890ABCDEF' for c in s.upper())

    @staticmethod
    async def is_float(s):
        return re.match(r'^-?\d+(?:\.\d+)?$', s) is not None

    @staticmethod
    async def is_running(process_name, strict=False):
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

    @staticmethod
    async def is_on_whitelist(funcom_id):
        try:
            with open(WHITELIST_PATH, 'r') as f:
                lines = f.readlines()
        except:
            return False
        funcom_id = funcom_id.upper()
        for line in lines:
            if funcom_id in line.upper():
                return True
        return False

    @staticmethod
    async def update_whitelist_file(funcom_id, add=True):
        is_on_whitelist = await is_on_whitelist(funcom_id)
        if (is_on_whitelist and add) or (not is_on_whitelist and not add):
            return
        try:
            with open(WHITELIST_PATH, 'r') as f:
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
        with open(WHITELIST_PATH, 'w') as f:
            f.writelines(wlist)

    @staticmethod
    async def whitelist_player(funcom_id):
        # intercept obvious wrong cases
        if not await RCon.is_hex(funcom_id) or len(funcom_id) < 14 or len(funcom_id) > 16:
            return f"{funcom_id} is not a valid FuncomID."
        elif funcom_id == "8187A5834CD94E58":
            return f"{funcom_id} is the example FuncomID of Midnight."

        # try whitelisting via rcon
        msg = "Whitelisting failed. Server didn't respond. Please try again later."
        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                msg = mcr.command(f"WhitelistPlayer {funcom_id}")
            if msg == f"Player {funcom_id} added to whitelist.":
                return msg
        except:
            pass

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
        if write2file and not await RCon.is_running('ConanSandboxServer'):
            await RCon.update_whitelist_file(funcom_id)
            msg = f"Player {funcom_id} added to whitelist."
        # try again later
        elif write2file:
            msg = f"Server is not ready. Please try again later."
        return msg

    @staticmethod
    async def unwhitelist_player(funcom_id):
        msg = "Unwhitelisting failed. Server didn't respond. Please try again later."
        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                msg = mcr.command(f"UnWhitelistPlayer {funcom_id}")
            if msg == f"Player {funcom_id} removed from whitelist.":
                return msg
        except:
            pass

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
        if write2file and not await RCon.is_running('ConanSandboxServer'):
            await RCon.update_whitelist_file(funcom_id, add=False)
            msg = f"Player {funcom_id} removed from whitelist."
        # try again later
        elif write2file and await RCon.is_running('ConanSandboxServer'):
            msg = f"Server is not ready. Please try again later."
        return msg

    @staticmethod
    async def update_user(funcom_id, member):
        removed = []
        # get all users who share either of the three attributes
        users = session.query(Users).filter(
            (Users.disc_id==member.id) |
            (Users.disc_user==str(member)) |
            (Users.funcom_id==funcom_id)).all()
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
    async def is_time_format(time):
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

    @staticmethod
    async def get_time_decimal():
        logger.info(f"Trying to read the time from the game server.")
        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                time = mcr.command(f"TERPO getTimeDecimal")
                if not await RCon.is_float(time):
                    logger.info(f"Failed reading time. {time}")
                    return 2
                logger.info(f"Time read successfully: {time}")
                saved.LAST_RESTART_TIME = time
                return 0
        except Exception as err:
            if len(err.args) >= 2:
                logger.error(f"Failed to read time from game server. RConError: err.args[1] == {err.args[1]}")
            else:
                logger.error(f"Failed to read time from game server. RConError: err.args == {err.args}")
            return 1

    @staticmethod
    async def set_time_decimal():
        time = saved.LAST_RESTART_TIME
        logger.info(f"Trying to reset the time to the previously read time of {time}")
        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                msg = mcr.command(f"TERPO setTimeDecimal {time}")
                if not msg.startswith("Time has been set to"):
                    logger.info(f"Failed setting time. {msg}")
                    return 2
                logger.info("Time was reset successfully!")
                return 0
        except Exception as err:
            if len(err.args) >= 2:
                logger.error(f"Failed to set time {time}. RConError: err.args[1] == {err.args[1]}")
            else:
                logger.error(f"Failed to set time {time}. RConError: err.args == {err.args}")
            return 1

    @command(name='listplayers', help="Shows a list of all players online right now")
    async def listplayers(self, ctx):
        def rreplace(s, old, new):
            li = s.rsplit(old, 1)
            return new.join(li)

        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                playerlist = mcr.command("ListPlayers")
        except Exception as err:
            await ctx.send("RCon error retrieving the playerlist, please try again in a few seconds.")
            if len(err.args) >= 2:
                logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args[1] == {err.args[1]}")
            else:
                logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args == {err.args}")
            return
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
        num = len(names)
        if num == 0:
            await ctx.send("Nobody is currently online")
        elif num < 20:
            await ctx.send(f"__**Players online:**__ {len(names)}\n" + '\n'.join(names))
        else:
            await ctx.send(rreplace(f"__**Players online:**__ {len(names)}\n" + ', '.join(names), ",", " and"))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name='whitelist', help="Whitelists the player using the given FuncomID")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whitelist(self, ctx, FuncomID, *Player):
        def rreplace(s, old, new):
            li = s.rsplit(old, 1)
            return new.join(li)

        funcom_id = await Applications.get_funcom_id_in_text(FuncomID)
        if not funcom_id:
            msg = "No valid FuncomID given. ID needs to be 14-16 characters long and consist only of digits and letters A-F."
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return

        member = await General.get_member(ctx, " ".join(Player))
        if not member:
            msg = f"Couldn't get id for {Player}. Are you sure they are still on this discord server?"
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        success = await RCon.update_user(funcom_id, member)
        if not success:
            msg = f"Failed to whitelist. FuncomID already in use by another player."
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        removed = None
        if type(success) is list:
            removed = success
            for id in removed:
                result = await RCon.unwhitelist_player(id)
                if not result.endswith("removed from whitelist."):
                    await ctx.send(f"Unwhitelisting former FuncomID {id} failed. Server didn't respond. Please try again later.")
        msg = await RCon.whitelist_player(funcom_id)
        if not msg.endswith("added to whitelist."):
            msg = f"Whitelisting failed. Server didn't respond. Please try again later."
        else:
            if removed:
                r = "FuncomID " + removed[0] + " was" if len(removed) == 1 else "FuncomIDs " + removed[0] + " and " + removed[1] + " were"
                msg += f" Previous {r} removed from whitelist."
        await ctx.send(msg)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")

    @command(name='whitelistall', help="Whitelists everyone who's currently in the supplemental database. Only works while server is down.")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whitelistall(self, ctx):
        if await RCon.is_running("ConanSandboxServer"):
            await ctx.send("Command can only be used while server isn't running.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
            return
        # try to read all entries already in the whitelist.txt file
        try:
            with open(WHITELIST_PATH, 'r') as f:
                lines = f.readlines()
        # if file doesn't exist create an empty list
        except:
            with open(WHITELIST_PATH, 'w') as f:
                pass
            lines = []

        # split lines into id and name. Remove duplicates.
        filtered = set()
        names = {}
        # define regular expression to filter out unprintable characters
        control_chars = ''.join(map(chr, itertools.chain(range(0x00,0x20), range(0x7f,0xa0))))
        control_char_re = re.compile('[%s]' % re.escape(control_chars))
        for line in lines:
            if line != "\n" and not "INVALID" in line:
                # remove unprintable characters from the line
                res = control_char_re.sub('', line)
                res = res.split(':')
                id = res[0].strip()
                if len(res) > 1:
                    name = res[1].strip()
                else:
                    name = 'Unknown'
                filtered.add(id)
                # if duplicate values exist, prioritize those containing a funcom_name
                if not id in names or names[id] == 'Unknown':
                    names[id] = name

        # go through the Users table and supplement missing users if any
        for user in session.query(Users).all():
            if not user.funcom_id in filtered:
                filtered.add(user.funcom_id)
                names[user.funcom_id] = 'Unknown'

        # create lines to write into new whitelist.txt
        wlist = []
        for id in filtered:
            wlist.append(id + ':' + names[id] + '\n')
            wlist.sort()

        # overwrite / write the new file with the contenst of wlist
        with open(WHITELIST_PATH, 'w') as f:
            f.writelines(wlist)
        await ctx.send("All players in the supplemental database have been placed on the whitelist.")

    @command(name='gettime', help="Tells the current time on the server")
    async def gettime(self, ctx):
        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                time = mcr.command("TERPO getTime")
        except Exception as err:
            if len(err.args) >= 2:
                logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args[1] == {err.args[1]}")
            else:
                logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args == {err.args}")
            return
        if time == 'Still processing previous command.':
            await ctx.send("Still processing previous command. Try again in a few seconds.")
            return
        # end conversion to human readable representation
        await ctx.send(f"It's currently {time} on the server.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Current server time was sent to {ctx.author}.")

    @command(name='settime', help="Sets the time on the server")
    @has_role(ADMIN_ROLE)
    async def settime(self, ctx, Time):
        time = await RCon.is_time_format(Time)
        if not time:
            await ctx.send("Bad time format. Please enter time in HH[:MM[:SS]] 24h format.")
            return
        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                time = mcr.command(f"TERPO setTime {time}")
        except Exception as err:
            if len(err.args) >= 2:
                logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args[1] == {err.args[1]}")
            else:
                logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args == {err.args}")
            return
        if len(Time) <= 5:
            time = time[:-3]
        await ctx.send(f"Time on the server has been set to {time}.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Current server time was set to {time} by {ctx.author}.")

def setup(bot):
    bot.add_cog(RCon(bot))
