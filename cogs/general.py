from discord.ext import commands
from discord.ext.commands import command
from logger import logger
from exiles_api import *
from config import *
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
    @has_not_role(NOT_APPLIED_ROLE)
    async def setsteamid(self, ctx, SteamID64: str):
        steam_id = SteamID64
        if not steam_id.isnumeric() or len(steam_id) != 17:
            raise NotSteamIdError()
        elif steam_id == "76561197960287930":
            raise IsGabesIDError()
        users = session.query(Users).filter((Users.steam_id==steam_id) | (Users.disc_user==str(ctx.author))).all()
        if len(users) > 1:
            await ctx.send(f"SteamID64 {steam_id} has already been registered by another user. Please make sure this is really yours. If you are sure, please contact an admin for clarification.")
            return
        elif len(users) == 1:
            users[0].steam_id = steam_id
        else:
            session.add(Users(steam_id=steam_id, disc_user=str(ctx.author)))
        session.commit()
        logger.info(f"Player {ctx.author} set their SteamID64 to {steam_id}.")
        await ctx.channel.send(f"Your SteamID64 has been set to {steam_id}.")

    @command(name="getsteamid", help="Checks if your SteamID64 has been set.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def getsteamid(self, ctx):
        disc_user = await commands.MemberConverter().convert(ctx, ctx.author.mention)
        player = Player(disc_user=str(disc_user))
        if player.steam_id:
            await ctx.channel.send(f"Your SteamID64 is currently set to {player.steam_id}.")
        else:
            await ctx.channel.send(f"Your SteamID64 has not been set yet. You can set it with `{PREFIX}setsteamid <SteamID64>`")

    @command(name="whois", help="Tells you the chararacter name(s) belonging to the given discord user or vice versa")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whois(self, ctx, *, arg):
        if len(arg) > 5 and arg[-5] == '#':
            player = Player(disc_user=arg)
            if not player.characters:
                char = session.query(Characters).filter_by(name=arg).first()
                if char:
                    player = char.player
        elif arg[:3] == "<@!" and arg[-1] == '>':
            try:
                disc_user = await commands.MemberConverter().convert(ctx, arg)
            except:
                pass
            if disc_user:
                player = Player(disc_user=disc_user)
        else:
            player = Player(disc_user=arg)
            if not player.characters:
                char = session.query(Characters).filter(func.lower(Characters.name).like('%' + arg.lower() + '%')).first()
                if char:
                    player = char.player
        if not player.characters:
            msg = f"No discord user or character {arg} has been found."
        else:
            msg = f"The characters belonging to the discord nick **{player.disc_user}** are:\n"
            for char in player.characters:
                lldate = char.last_login.strftime("%d-%b-%Y %H:%M:%S UTC")
                if char.slot == 'active':
                    msg += f"**{char.name}** on **active** slot (last login: {lldate})\n"
                else:
                    msg += f"**{char.name}** on slot **{char.slot}** (last login: {lldate})\n"
        await ctx.send(msg)

    @command(name="claim", help="Claim your character to enable character switching. Requires your SteamID64 to be set first.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def claim(self, ctx, Name: str):
        name = Name
        user = session.query(Users).filter(Users.disc_user==str(ctx.author)).first()
        if not user:
            await ctx.send(f"Please use `{PREFIX}setsteamid <SteamID64>` to set your 17 digit SteamID64 first.")
            return
        char = session.query(Characters).filter(func.lower(Characters.name)==name.lower()).first()
        if not char:
            await ctx.send(f"Couldn't find a character named {name} in the database. Please verify that your spelling is correct and that you have already created this character.")
            return
        account = session.query(Account).get(char.pure_player_id)
        if not account:
            await ctx.send("Couldn't link character to your account. Please notify an admin of your failed attempt for further investigations.")
            logger.error(f"No account data for player with player_id {char.pure_player_id} and name {name} was found. This should never be the case, please investigate!")
            return
        steam64 = session.query(Steam64).filter_by(funcom_id=account.funcom_id).first()
        if steam64:
            if steam64.id == user.steam_id:
                await ctx.send(f"This character is already linked to your FuncomID. You only need to link your first character, all additional characters will automatically be added. To check which characters are linked to your account please use `{PREFIX}mychars`.")
                logger.info(f"Player {ctx.author} tried to link character with player_id {char.pure_player_id} and name {name} which were already linked to their FuncomID {account.funcom_id}.")
                return
            await ctx.send("The character you were trying to claim has already claimed by someone else. If the character is really yours (and there is no other one with the same name), please notify an admin for further investigations.")
            logger.info(f"Player {ctx.author} tried to link character with player_id {char.pure_player_id} and name {name} which were already linked to FuncomID {account.funcom_id} belonging to another player.")
            return
        user.funcom_id = account.funcom_id
        user.player_id = char.pure_player_id
        steam64 = Steam64(id=user.steam_id, funcom_id=account.funcom_id)
        session.add(steam64)
        session.commit()
        logger.info(f"Player {ctx.author} linked SteamID64 {user.steam_id} to the funcom_id {account.funcom_id}.")
        await ctx.channel.send(f"Your character {char.name} has been successfully linked to your FuncomID.")

    @command(name="mychars", help="Check which chars have already been linked to your FuncomID.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def mychars(self, ctx):
        user = session.query(Users).filter_by(disc_user=str(ctx.author)).first()
        if not user or not user.steam_id:
            await ctx.send(f"SteamID64 has not been set yet. Please use `{PREFIX}setsteamid <SteamID64` to set your SteamID64. Then you can claim your character with `{PREFIX}claim <character name>`.")
            logger.info(f"Player {ctx.author} tried to check their chars but hasn't set SteamID64 or linked their characters yet.")
            return
        steam64 = session.query(Steam64).filter_by(id=user.steam_id).first()
        if not steam64 or not steam64.funcom_id:
            await ctx.send(f"You have not linked your FuncomID to your characters yet. Please use the `{PREFIX}claim <character name>` command to do son and enable the character switch feature.")
            logger.info(f"Player {ctx.author} tried to check their chars but hasn't linked them to their FuncomID yet.")
            return
        if not user.funcom_id:
            user.funcom_id = steam64.funcom_id
            session.commit()
        if not user.player_id:
            result = session.query(Account).filter_by(funcom_id=steam64.funcom_id).first()
            if not result:
                await ctx.send("Couldn't link character to your FuncomID. Please notify an admin as this should never happen.")
                logger.error(f"No account data for player with funcom_id {steam64.funcom_id}, steam_id {steam64.id} and disc_user {ctx.author} was found. This should never be the case, please investigate!")
                return
            user.player_id = result.player_id
            session.commit()
        # print(f"player_id: {user.player_id} / funcom_id: {user.funcom_id} / steam_id: {steam64.id} / disc_user: {str(ctx.author)}")
        player = Player(id=user.player_id, funcom_id=user.funcom_id, steam_id=steam64.id, disc_user=str(ctx.author))
        msg = f"The characters belonging to your account are:\n"
        for char in player.characters:
            lldate = char.last_login.strftime("%d-%b-%Y %H:%M:%S UTC")
            if char.slot == 'active':
                msg += f"**{char.name}** on **active** slot (last login: {lldate})\n"
            else:
                msg += f"**{char.name}** on slot **{char.slot}** (last login: {lldate})\n"
        await ctx.send(msg)

def setup(bot):
    bot.add_cog(General(bot))
