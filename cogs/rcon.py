from discord import Member
from discord.ext import commands
from discord.ext.commands import command
from valve import rcon
import config as cfg
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
            playerlist = rcon.execute((cfg.RCON_IP, cfg.RCON_PORT), cfg.RCON_PASSWORD, "ListPlayers")
        except Exception as error:
            print("excetion raised", type(error), error.args[1])
            raise RConConnectionError(error.args[1])
        print("playerlist:", playerlist)
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
    @has_role(cfg.ADMIN_ROLE)
    async def whitelist(self, ctx, Player: Member, SteamID64: int):
        result = await whitelist_player(SteamID64, Player)
        if result == "NotSteamIdError":
            raise NotSteamIdError()
        elif result == "IsGabesIDError":
            raise IsGabesIDError()
        elif result.find("FailedError") >= 0:
            raise commands.BadArgument(result[12:])
        else:
            await ctx.send(result)
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            logger.info(f"ERROR: Author: {ctx.author} / Command: {ctx.message.content}. {result}")

def setup(bot):
    bot.add_cog(RCon(bot))
