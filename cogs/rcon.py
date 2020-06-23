from discord import Member
from discord.ext import commands
from discord.ext.commands import command
from threading import Timer
from valve import rcon
from config import *
from logger import logger
from exceptions import *
from checks import *
from helpers import *

class RCon(commands.Cog, name="RCon commands"):
    def __init__(self, bot):
        self.bot = bot

    @command(name='listplayers', help="Shows a list of all players online right now")
    async def listplayers(self, ctx):
        try:
            playerlist = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, "ListPlayers")
        except Exception as error:
            print("excetion raised", type(error), error.args[1])
            raise RConConnectionError(error.args[1])
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
            await ctx.send(rreplace(f"__**Players online:**__ {len(names)}\n" + ', '.join(names), ",", " and", 1))

    @command(name='whitelist', help="Whitelists the player with the given discord nick and SteamID64")
    @has_role(ADMIN_ROLE)
    async def whitelist(self, ctx, Player: Member, SteamID64: int):
        result = await whitelist_player(ctx, SteamID64, Player)
        if result == "NotSteamIdError":
            raise NotSteamIdError()
        elif result == "IsGabesIDError":
            raise IsGabesIDError()
        elif result.find("FailedError") >= 0:
            raise commands.BadArgument(result[12:])
        else:
            await ctx.send(result)
            print(f"ERROR: Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")

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
        time = await is_time_format(Time)
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
