from discord.ext import commands
from discord.ext.commands import command
import config as cfg
from logger import logger
from db import sessionSupp, Users
from exceptions import *
from checks import *
from helpers import *

class General(commands.Cog, name="General commands"):
    def __init__(self, bot):
        self.bot = bot

    @command(name='roll', help="Rolls a dice in NdN format")
    async def roll(self, ctx, *, Dice: str):
        result = await roll_dice(Dice)
        await ctx.send(f"{ctx.author.mention} rolled: " + result)

    @command(name="setsteamid", help="Set your 17 digit SteamID64 (the one used to whitelist you)")
    @has_not_role(cfg.NOT_APPLIED_ROLE)
    async def setsteamid(self, ctx, SteamID64: str):
        if not SteamID64.isnumeric() or len(SteamID64) != 17:
            raise NotSteamIdError()
        elif SteamID64 == "76561197960287930":
            raise IsGabesIDError()
        sessionSupp.query(Users).filter(or_(Users.SteamID64==SteamID64, Users.disc_user==str(ctx.author))).delete()
        sessionSupp.add(Users(SteamID64=SteamID64, disc_user=str(ctx.author)))
        sessionSupp.commit()
        logger.info(f"Player {ctx.author} set their SteamID64 to {SteamID64}.")
        await ctx.channel.send(f"Your SteamID64 has been set to {SteamID64}.")

    @command(name="getsteamid", help="Checks if your SteamID64 has been set.")
    @has_not_role(cfg.NOT_APPLIED_ROLE)
    async def getsteamid(self, ctx):
        disc_user = await commands.MemberConverter().convert(ctx, ctx.author.mention)
        SteamID64 = get_steamID64(disc_user)
        if SteamID64:
            await ctx.channel.send(f"Your SteamID64 is currently set to {SteamID64}.")
        else:
            await ctx.channel.send(f"Your SteamID64 has not been set yet. You can set it with `{cfg.PREFIX}setsteamid <SteamID64>`")

    @command(name="whois", help="Tells you the chararacter name(s) belonging to the given discord user or vice versa")
    @has_role_greater_or_equal(cfg.SUPPORT_ROLE)
    async def whois(self, ctx, *, arg):
        msg = None
        if len(arg) > 5 and arg[-5] == '#':
            result = sessionSupp.query(Users.SteamID64, Users.disc_user) \
                                .filter(func.lower(Users.disc_user)==arg.lower()) \
                                .first()
            if not result:
                msg, disc_user = ("No character belonging to that discord nick has been found.", None)
            else:
                SteamID64, disc_user = result
        elif arg[:3] == "<@!" and arg[-1] == '>':
            try:
                SteamID64, disc_user = (None, await commands.MemberConverter().convert(ctx, arg))
            except:
                msg, disc_user = ("No character belonging to that discord nick has been found.", None)
        else:
            result = sessionSupp.query(Users.SteamID64, Users.disc_user) \
                                .filter(func.lower(Users.disc_user) \
                                .like(arg.lower() + "#____")) \
                                .first()
            SteamID64, disc_user = result if result else (None, None)

        if disc_user and not msg:
            msg = f"The characters belonging to the discord nick **{disc_user}** are:\n"
            SteamID64 = SteamID64 or get_steamID64(disc_user)
            if SteamID64:
                characters = get_char(SteamID64)
                if characters:
                    for char in characters:
                        if char['slot'] == 'active':
                            msg += f"**{char['name']}** on active slot (last login: {char['lastLogin']})\n"
                        else:
                            msg += f"**{char['name']}** on slot {char['slot']} (last login: {char['lastLogin']})\n"
                else:
                    msg = "No character belonging to that discord nick has been found."
            else:
                msg = "No character belonging to that discord nick has been found."
        elif not msg:
            SteamID64 = get_steamID64(arg)
            if SteamID64:
                disc_user = get_disc_user(SteamID64)
                if disc_user:
                    msg = f"The discord nick of the player of {arg} is **{disc_user}**"
                else:
                    msg = "No discord nick associated with that character has been found"
            else:
                msg = f"No character named {arg} has been found"
        await ctx.channel.send(msg)

def setup(bot):
    bot.add_cog(General(bot))
