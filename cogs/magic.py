from discord.ext import commands
from discord.ext.commands import command, group
from logger import logger
from checks import *
from config import *
from exiles_api import *
from functions import *

class Mag(commands.Cog, name="Magic commands."):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def get_mchar(character):
        if type(character) is int or character.isnumeric():
            mchar = session.query(MagicChars).get(character)
            if mchar:
                mchars = [mchar]
            else:
                return f"No character with ID **{character}** registered."
        else:
            mchars = session.query(MagicChars).filter(MagicChars.name.collate('NOCASE')==character).all()
        if len(mchars) == 0:
            return f"No character named **{character}** registered."
        elif len(mchars) > 1:
            return f"Character name **{character}** is ambiguous. Please use character ID instead."
        return mchars[0]

    @staticmethod
    async def get_char(character):
        if type(character) is int or character.isnumeric():
            char = session.query(Characters).get(character)
            if char:
                chars = [char]
            else:
                return f"No character with ID **{character}** found."
        else:
            chars = session.query(Characters).filter(Characters.name.collate('NOCASE')==character).all()
        if len(chars) == 0:
            return f"No character named **{character}** found."
        elif len(chars) > 1:
            return f"Character name **{character}** is ambiguous. Please use character ID instead."
        return chars[0]

    @staticmethod
    async def get_char_by_user(user, single_only=True):
        chars = []
        for char in user.characters:
            mchar = session.query(MagicChars).get(char.id)
            if mchar and mchar.active:
                chars.append(mchar)
        if len(chars) > 0 and not single_only:
            return chars
        elif len(chars) == 0:
            return f"No registered magic character belonging to **{user.disc_user}** found."
        elif len(chars) > 1:
            return f"User **{user.disc_user}** has more than one registered magic character. Please specify character name."
        return chars[0]

    @group(help="Commands to roll for and keep track of the mana for magic using chars.")
    async def mag(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(f"No such subcommand found. Type {PREFIX}help mag for more info on mag subcommands.")

    @mag.command(name='add', help="Registers a character with the system.")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def add(self, ctx, *, Character):
        # determine the char by its name or id or return an error message if none were found
        result = await Mag.get_char(Character)
        if type(result) is str:
            await ctx.send(result)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
            return
        char = result
        # ensure that this char isn't already registered and active
        mchar = session.query(MagicChars).get(char.id)
        if mchar and char.name != mchar.name:
            mchar.name = char.name
            if not mchar.active:
                mchar.active = True
                await ctx.send(f"Registered **{char.name}** as magic user.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Registered {char.name} as magic user.")
            else:
                await ctx.send(f"Character is already registered under name **{mchar.name}**. Name has been updated to **{char.name}**.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Character is already registered under name {mchar.name}. Name has been updated to {char.name}.")
            session.commit()
            return
        elif mchar:
            if not mchar.active:
                mchar.active = True
                await ctx.send(f"Registered **{char.name}** as magic user.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Registered {char.name} as magic user.")
                session.commit()
            else:
                await ctx.send("Character is already registered. No changes were made.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Character is already registered. No changes were made.")
            return
        # add character to the table
        mchar = MagicChars(id=char.id, name=char.name)
        session.add(mchar)
        session.commit()
        await ctx.send(f"Registered **{char.name}** as a magic user.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Registered {char.name} as a magic user.")

    @mag.command(name='remove', help="Unregisters a character from the system.")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def remove(self, ctx, *, Character):
        # determine the mchar by its name or id or return an error message if none were found
        result = await Mag.get_mchar(Character)
        # output error message if char wasn't found
        if type(result) is str:
            await ctx.send(result)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
            return
        mchar = result

        # determine the char by its id or return an error message if none were found
        result = await Mag.get_char(mchar.id)
        # delete character from MagicChars if it's no longer in Characters
        if type(result) is str:
            name = mchar.name
            session.delete(mchar)
        # deactivate character
        else:
            name = result.name
            mchar.active = False

        session.commit()
        await ctx.send(f"Unregistered **{name}**.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Unregistered {name}.")

    @mag.command(name='use', help="Subtracts the given number of mana points from the characters mana pool.")
    async def use(self, ctx, Mana: int, *Character):
        character = ' '.join(Character)
        # determine the char by its discord user
        if character == '':
            users = Users.get_users(ctx.author.id)
            if not users:
                await ctx.send("No characters linked to your discord account have been found.")
                return
            user = users[0]
            result = await Mag.get_char_by_user(user)
            if type(result) is str:
                await ctx.send(result)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
                return
        else:
            # determine the char by its name or id or return an error message if none were found
            result = await Mag.get_char(character)
            if type(result) is str:
                await ctx.send(result)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
                return
        char = result
        # ensure that this char is registered
        mchar = session.query(MagicChars).get(char.id)
        if not mchar or not mchar.active:
            await ctx.send(f"**{char.name}** is not registered. No changes were made.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} is not registered. No changes were made.")
            return
        elif mchar.mana < Mana:
            await ctx.send(f"**{char.name}** does not have enough mana. Mana points left this week: **{mchar.mana}**.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} does not have enough mana. Mana points left this week: {mchar.mana}.")
            return
        mchar.mana -= Mana
        mchar.total_uses += 1
        mchar.total_spent += Mana
        mchar.last_use = Mana
        session.commit()
        mp = "mana point" if Mana == 1 else "mana points"
        await ctx.send(f"**{char.name}** used **{Mana}** {mp}. Mana points left this week: **{mchar.mana}**.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} used {Mana} {mp}. Mana points left this week: {mchar.mana}.")

    @mag.command(name='give', help="Adds the given number of mana points to the characters mana pool.")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def give(self, ctx, Mana: int, *Character):
        character = ' '.join(Character)
        # determine the char by its discord user
        if character == '':
            await ctx.send("Character is a required argument that is missing.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Character is a required argument that is missing.")
            return
        # determine the char by its name or id or return an error message if none were found
        result = await Mag.get_char(character)
        if type(result) is str:
            await ctx.send(result)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
            return
        char = result
        # ensure that this char is registered
        mchar = session.query(MagicChars).get(char.id)
        if not mchar or not mchar.active:
            await ctx.send(f"**{char.name}** is not registered. No changes were made.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} is not registered. No changes were made.")
            return
        mchar.mana += Mana
        session.commit()
        mp = "mana point" if Mana == 1 else "mana points"
        await ctx.send(f"**{char.name}** was given **{Mana}** {mp}. Mana points left this week: **{mchar.mana}**.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} was given {Mana} {mp}. Mana points left this week: {mchar.mana}.")

    @mag.command(name='undo', help="Reverts the last mana use.")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def undo(self, ctx, *Character):
        character = ' '.join(Character)
        # determine the char by its discord user
        if character == '':
            await ctx.send("Character is a required argument that is missing.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Character is a required argument that is missing.")
            return
        # determine the char by its name or id or return an error message if none were found
        result = await Mag.get_char(character)
        if type(result) is str:
            await ctx.send(result)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
            return
        char = result
        # ensure that this char is registered
        mchar = session.query(MagicChars).get(char.id)
        if not mchar or not mchar.active:
            await ctx.send(f"**{char.name}** is not registered. No changes were made.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} is not registered. No changes were made.")
            return
        elif not mchar.last_use:
            await ctx.send(f"**{char.name}** has not used any mana so far or there is no record of it. No changes were made.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} has not used any mana so far or there is no record of it. No changes were made.")
            return
        given = mchar.last_use
        mchar.mana += given
        mchar.total_uses -= 1
        mchar.total_spent -= given
        mchar.last_use = None
        session.commit()
        mp = "mana point" if given == 1 else "mana points"
        await ctx.send(f"**{char.name}** was given back **{given}** {mp}. Mana points left this week: **{mchar.mana}**.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} was given {given} {given}. Mana points left this week: {mchar.mana}.")

    @mag.command(name='stats', help=f"Shows statistics for all or a single character or resets them for a single character")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def stats(self, ctx, *args):
        # reset the stats for the given char
        if len(args) > 0 and args[0] == 'reset':
            name = ' '.join(args[1:])
            if name == '':
                await ctx.send("Character is a required argument that is missing.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. Character is a required argument that is missing.")
                return
            result = await Mag.get_char(name)
            if type(result) is str:
                await ctx.send(result)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
                return
            char = result
            # ensure that this char is registered
            mchar = session.query(MagicChars).get(char.id)
            if not mchar or not mchar.active:
                await ctx.send(f"**{char.name}** is not registered. No changes were made.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} is not registered. No changes were made.")
                return
            mchar.mana = 0
            mchar.total_uses = 0
            mchar.total_spent = 0
            mchar.last_use = None
            session.commit()
            await ctx.send(f"**{char.name}** has been reset to 0 mana and 0 uses.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} has been reset to 0 mana and 0 uses.")
        # display the stats for the given character
        elif len(args) > 0:
            character = ' '.join(args)
            # determine the char by its discord user
            result = await Mag.get_char(character)
            if type(result) is str:
                await ctx.send(result)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
                return
            char = result
            # ensure that this char is registered
            mchar = session.query(MagicChars).get(char.id)
            if not mchar or not mchar.active:
                await ctx.send(f"**{char.name}** is not registered. No changes were made.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} is not registered. No changes were made.")
                return
            mp = "mana point" if mchar.mana == 1 else "mana points"
            tm = "time" if mchar.total_uses == 1 else "times"
            sp = "mana point" if mchar.total_spent == 1 else "mana points"
            await ctx.send(f"**{char.name}** has **{mchar.mana}** {mp} left this week, used mana **{mchar.total_uses}** {tm} and spent **{mchar.total_spent}** {sp} that way since registration.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {char.name} has {mchar.mana} {mp} left this week, used mana {mchar.total_uses} {tm} and spent {mchar.total_spent} {sp} that way since registration.")
        # display the stats for all registered users
        else:
            mchars = session.query(MagicChars).filter_by(active=True).order_by(MagicChars.name).all()
            if len(mchars) == 0:
                await ctx.send("No magic chars registered.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. No magic chars registered.")
                return
            longest_name = session.query(func.max(func.length(MagicChars.name))).filter_by(active=True).scalar()
            hd = ["Character", " mana points", "total uses", "total spent"]
            wd = longest_name if longest_name > len(hd[0]) else len(hd[0])
            output = (f"```"
                      f"{hd[0]:<{wd}} | "
                      f"{hd[1]:>{len(hd[1])}} | "
                      f"{hd[2]:>{len(hd[2])}} | "
                      f"{hd[3]:>{len(hd[3])}}")
            output += '\n' + '-' * (len(output) - 3)
            for mchar in mchars:
                chunk = (f"\n{mchar.name:<{wd}} | "
                         f"{mchar.mana:>{len(hd[1])}} | "
                         f"{mchar.total_uses:>{len(hd[2])}} | "
                         f"{mchar.total_spent:>{len(hd[3])}}")
                # ensure that the whole output isn't longer than 2000 characters
                if (len(output) + len(chunk)) >= 2000:
                    await ctx.send(output)
                    output = chunk
                else:
                    output += chunk
            await ctx.send(output + "```")

    @mag.command(name='mana', help="Tells you how much mana you have left this week.")
    async def mana(self, ctx):
        users = Users.get_users(ctx.author.id)
        if not users:
            await ctx.send("No characters linked to your discord account have been found.")
            return
        user = users[0]
        result = await Mag.get_char_by_user(user, single_only=False)
        if type(result) is str:
            await ctx.send(result)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}.")
            return
        mchars = result
        output = []
        for mchar in mchars:
            if mchar and mchar.active:
                mp = "mana point" if mchar.mana == 1 else "mana points"
                output.append(f"**{mchar.name}** has **{mchar.mana}** {mp} left this week.")
        if len(output) > 0:
            await ctx.send('\n'.join(output))
        else:
            await ctx.send(f"No registered characters found.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. No registered characters found.")
            return

def setup(bot):
    bot.add_cog(Mag(bot))
