import sys, re
from discord import Member
from discord.ext import commands
from discord.ext.commands import command
from threading import Timer
from psutil import process_iter
from valve import rcon
from config import *
from exiles_api import *
from logger import logger
from exceptions import *
from checks import *
from cogs.general import General

class RCon(commands.Cog, name="RCon commands"):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
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

    @staticmethod
    def whitelist_player(funcom_id):
        msg = "Whitelisting failed. Server didn't respond. Please try again later."
        try:
            msg = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, f"WhitelistPlayer {funcom_id}")
            if msg == f"Player {funcom_id} added to whitelist.":
                return msg
        except:
            pass
        # when server is completely down and doesn't react
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
            print(f"Error: {msg}")
            logger.error(msg)
            return msg
        if write2file and not RCon.is_running('ConanSandboxServer'):
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
            for line in lines:
                if line != "\n" and not "INVALID" in line:
                    res = line.split(':')
                    id = res[0].strip()
                    if len(res) > 1:
                        name = res[1].strip()
                    else:
                        name = 'Unknown'
                    filtered.add(id)
                    if not id in names or names[id] == 'Unknown':
                        names[id] = name
            filtered.add(funcom_id)
            names[funcom_id] = 'Unknown'
            wlist = []
            for id in filtered:
                wlist.append(id + ':' + names[id] + '\n')
            with open(WHITELIST_PATH, 'w') as f:
                f.writelines(wlist)
            msg = f"Player {funcom_id} added to whitelist."
        elif write2file and RCon.is_running('ConanSandboxServer'):
            msg = f"Server is not ready. Please try again later."
        return msg

    @staticmethod
    def unwhitelist_player(funcom_id):
        msg = "Unwhitelisting failed. Server didn't respond. Please try again later."
        try:
            msg = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, f"UnWhitelistPlayer {funcom_id}")
            if msg == f"Player {funcom_id} removed from whitelist.":
                return msg
        except:
            pass
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
            print(f"Error: {msg}")
            logger.error(msg)
            return msg
        if write2file and not RCon.is_running('ConanSandboxServer'):
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
            for line in lines:
                if line != "\n" and not "INVALID" in line and not funcom_id in line:
                    res = line.split(':')
                    id = res[0].strip()
                    if len(res) > 1:
                        name = res[1].strip()
                    else:
                        name = 'Unknown'
                    filtered.add(id)
                    if not id in names or names[id] == 'Unknown':
                        names[id] = name
            wlist = []
            for id in filtered:
                wlist.append(id + ':' + names[id] + '\n')
            with open(WHITELIST_PATH, 'w') as f:
                f.writelines(wlist)
            msg = f"Player {funcom_id} removed from whitelist."
        elif write2file and RCon.is_running('ConanSandboxServer'):
            msg = f"Server is not ready. Please try again later."
        return msg

    @staticmethod
    def update_user(funcom_id, member):
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

    @staticmethod
    def set_time_decimal():
        logger.info(f"Trying to reset the time to the previously read time of {saved.LAST_RESTART_TIME}")
        try:
            rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, f"TERPO setTimeDecimal {saved.LAST_RESTART_TIME}")
            logger.info("Time was reset successfully!")
        except Exception as error:
            raise RConConnectionError(error.args[1])
        saved.LAST_RESTART_TIME = 12.0

    @command(name='listplayers', help="Shows a list of all players online right now")
    async def listplayers(self, ctx):
        def rreplace(s, old, new):
            li = s.rsplit(old, 1)
            return new.join(li)

        try:
            playerlist = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, "ListPlayers")
        except Exception as err:
            await ctx.send("RCon error retrieving the playerlist, please try again in a few seconds.")
            if hasattr(err, "args"):
                if len(err.args) >= 2:
                    print(f"ERROR: Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args[1] ==", err.args[1])
                    logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args[1] == {err.args[1]}")
                else:
                    print(f"ERROR: Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args ==", err.args)
                    logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: err.args == {err.args}")
            else:
                print(f"ERROR: Author: {ctx.author} / Command: {ctx.message.content}. RConError: sys.exc_info() ==", sys.exc_info()[1])
                logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. RConError: sys.exc_info() == {sys.exc_info()}")
            return
            # raise RConConnectionError(sys.exc_info()[0])
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
        print(f"Author: {ctx.author} / Command: {ctx.message.content}.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name='whitelist', help="Whitelists the player using the given FuncomID")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whitelist(self, ctx, FuncomID, *Player):
        def rreplace(s, old, new):
            li = s.rsplit(old, 1)
            return new.join(li)

        result = re.search(r'([a-fA-F0-9]{12,})', FuncomID)
        if not result:
            raise NotFuncomIdError
        funcom_id = result.group(1).upper()
        member = await General.get_member(ctx, " ".join(Player))
        if not member:
            await ctx.send(f"Couldn't get id for {Player}. Are you sure they are still on this discord server?")
            return
        success = self.update_user(funcom_id, member)
        if not success:
            await ctx.send(f"Failed to whitelist. FuncomID already in use by another player.")
            return
        removed = None
        if type(success) is list:
            removed = success
            for id in removed:
                RCon.unwhitelist_player(id)
        msg = RCon.whitelist_player(funcom_id)
        if not msg.endswith("added to whitelist."):
            msg = f"Whitelisting failed. Server didn't respond. Please try again later."
        else:
            if removed:
                r = "FuncomID " + removed[0] + " was" if len(removed) == 1 else "FuncomIDs " + removed[0] + " and " + removed[1] + " were"
                msg += f" Previous {r} removed from whitelist."
        await ctx.send(msg)
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")

    @command(name='whitelistme', help="Whitelists you using the given FuncomID")
    @has_not_role(NOT_APPLIED_ROLE)
    async def whitelistme(self, ctx, FuncomID):
        result = re.search(r'([a-fA-F0-9]{12,})', FuncomID)
        if not result:
            raise NotFuncomIdError
        funcom_id = result.group(1).upper()
        success = self.update_user(funcom_id, ctx.author)
        if not success:
            await ctx.send(f"Whitelisting failed. FuncomID already in use by another player.")
            return
        removed = None
        if type(success) is list:
            removed = success
            for id in removed:
                RCon.unwhitelist_player(id)
        msg = RCon.whitelist_player(funcom_id)
        if not msg.endswith("added to whitelist."):
            msg = "Whitelisting failed. Server didn't respond. Please try again later."
        else:
            msg = f"You have been whitelisted with FuncomID {funcom_id}."
            if removed:
                r = "FuncomID " + removed[0] + " was" if len(removed) == 1 else "FuncomIDs " + removed[0] + " and " + removed[1] + " were"
                msg += f" Previous {r} removed from whitelist."
        await ctx.send(msg)
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")

    @command(name='gettime', help="Tells the current time on the server")
    async def gettime(self, ctx):
        try:
            time = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, "TERPO getTimeDecimal")
        except Exception as error:
            print("exception raised", type(error), error.args[1])
            raise RConConnectionError(error.args[1])
        if time == 'Still processing previous command.':
            await ctx.send("Still processing previous command. Try again in a few seconds.")
            return
        # convert decimal representation to human readable one
        time = float(time)
        hours = str(int(time))
        seconds = (time % 1) * 3600
        minutes = str(int(seconds / 60)).zfill(2)
        seconds = str(int(seconds % 60)).zfill(2)
        time = f"{hours}:{minutes}:{seconds}"
        # end conversion to human readable representation
        await ctx.send(f"It's currently {time[:-3]} on the server.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. Current server time was sent to {ctx.author}.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Current server time was sent to {ctx.author}.")

    @command(name='settime', help="Sets the time on the server")
    @has_role(ADMIN_ROLE)
    async def settime(self, ctx, Time):
        time = self.is_time_format(Time)
        if not time:
            await ctx.send("Bad time format. Please enter time in HH[:MM[:SS]] 24h format.")
            return
        try:
            msg = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, f"TERPO setTime {time}")
        except Exception as error:
            print("excetion raised", type(error), error.args[1])
            raise RConConnectionError(error.args[1])
        if len(Time) <= 5:
            time = time[:-3]
        await ctx.send(f"Time on the server has been set to {time}.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. Current server time was set to {time} by {ctx.author}.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Current server time was set to {time} by {ctx.author}.")

def setup(bot):
    bot.add_cog(RCon(bot))
