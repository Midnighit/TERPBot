import random, config, time as saved
from math import ceil
from discord.ext import commands
from discord.ext.commands import command
from logger import logger
from exiles_api import *
from config import *
from exceptions import *
from checks import *

class General(commands.Cog, name="General commands."):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def print_iter(iter):
        if type(iter) == dict:
            print("{")
            for k, v in iter.items():
                print(f"    {k}: {v},")
            print("}")
        elif type(iter) == list:
            print("[")
            for idx in range(len(iter)):
                print(f"    {idx}: {iter[idx]},")
            print("]")

    @staticmethod
    async def get_guild_roles():
        roles = {}
        for role in saved.GUILD.roles:
            roles[role.name] = role
        return roles

    @staticmethod
    async def get_guild_categories():
        categories = {}
        for category in saved.GUILD.categories:
            categories[category.name] = categories
        return categories

    @staticmethod
    async def get_guild_channels():
        channels = {}
        for channel in saved.GUILD.channels:
            channels[channel.name] = channel
        return channels

    @staticmethod
    async def roll_dice(input):
        def rreplace(s, old, new, occurrence):
            li = s.rsplit(old, occurrence)
            return new.join(li)

        if input.find('d') == -1:
            raise NoDiceFormatError()
        input = input.replace(" ","")
        dice = Dice()
        num = ''
        type = 's'
        sign = '+'
        val = 0
        for c in input:
            if c in ('+', '-'):
                if type == 's' and num != '':
                    val = val - int(num) if sign == '-' else val + int(num)
                elif type == 's' and num == '':
                    pass
                elif num != '':
                    d.sides = int(num)
                    d.sign = sign
                    dice.append(d)
                else:
                    raise NoDiceFormatError()
                num = ''
                type = 's'
                sign = c
            elif c == 'd':
                d = Die(num=int(num)) if num != '' else Die()
                num = ''
                type = 'd'
            else:
                if not c.isnumeric():
                    raise NoDiceFormatError()
                num += c
        if type == 's' and num != '':
            val = val - int(num) if sign == '-' else val + int(num)
        elif num != '':
            d.sides = int(num)
            d.sign = sign
            dice.append(d)
        else:
            raise NoDiceFormatError()

        lst, sum = dice.roll()

        result = "**" + "**, **".join([str(r) for r in lst]) + "**"
        result = rreplace(result, ",", " and", 1)
        if val > 0:
            result = result + " + **" + str(val) + "**"
        elif val < 0:
            result = result + " - **" + str(abs(val)) + "**"
        result = f"{result} (total: **{str(sum + val)}**)" if len(lst) > 1 or val != 0 else result
        return result

    @staticmethod
    async def get_member(ctx, name):
        try:
            return await commands.MemberConverter().convert(ctx, name)
        except:
            try:
                return await commands.MemberConverter().convert(ctx, name.capitalize())
            except:
                return None

    @staticmethod
    async def get_user_string(arg, users, with_id=False):
        if not users:
            return f"No discord user or chracter named {arg} was found."

        msg = ''
        for user in users:
            id = '(@' + user.disc_id + ')' if with_id else ''
            if len(user.characters) == 0:
                msg += f"No characters linked to discord nick **{user.disc_user}** {id}have been found.\n"
            else:
                msg += f"The characters belonging to the discord nick **{user.disc_user}** {id} are:\n"
                for char in user.characters:
                    lldate = char.last_login.strftime("%d-%b-%Y %H:%M:%S UTC")
                    guild = f" is **{RANKS[char.rank]}** of clan **{char.guild.name}**" if char.has_guild else ''
                    slot = " on **active** slot" if char.slot == 'active' else f" on slot **{char.slot}**"
                    msg += f"**{char.name}**{guild}{slot} (last login: {lldate})\n"
                msg += '\n'
        return msg[:-2]

    @staticmethod
    async def get_clan_string(arg, guilds):
        if not guilds:
            return [f"No clan named {arg} was found."]

        msg = []
        chunk = ''
        for guild in guilds:
            members = guild.members
            if len(members) == 0:
                continue
            mem = 'members' if len(members) > 1 else 'member'
            chunk += f"Clan **{guild.name}** has **{len(members)}** {mem}:\n"
            members_by_rank = {}
            for member in members:
                rank = 3 if member.rank > 3 else member.rank
                if rank is None:
                    rank = -1
                if not rank in members_by_rank:
                    members_by_rank[member.rank] = [member]
                else:
                    members_by_rank[member.rank] += [member]
            for rank in range(3, -2, -1):
                if not rank in members_by_rank:
                    continue
                members = members_by_rank[rank]
                rank_nam = "Undeterminable rank" if rank == -1 else RANKS[rank]
                for member in members:
                    mem_msg = ''
                    lldate = member.last_login.strftime("%d-%b-%Y %H:%M:%S UTC")
                    slot = member.slot
                    if slot == 'active':
                        mem_msg += f"**{member.name}** is **{rank_nam}** on **active** slot (last login: {lldate})\n"
                    else:
                        mem_msg += f"**{member.name}** is **{rank_nam}** on slot **{slot}** (last login: {lldate})\n"

                    if len(chunk) + len(mem_msg) >= 2000:
                        msg.append(chunk)
                        chunk = mem_msg
                    else:
                        chunk += mem_msg
            if len(chunk) >= 1998:
                msg.append(chunk)
                chunk = '\n'
            else:
                chunk += '\n'

        msg.append(chunk)
        return msg

    @staticmethod
    async def get_owner_string(arg, thralls, loc=False, obj=False):
        if not thralls or len(thralls) == 0:
            return f"No thralls, pets or mounts with **{arg}** in their name were found."

        msg = f"Thralls, pets and mounts with **{arg}** in their name:\n"
        for key in sorted(thralls):
            thrall = thralls[key]
            owner_name = thrall['owner'].name if thrall['owner'] else "nobody"
            if owner_name == "":
                owner_name = "no name"
            msg += f"**{key}** is owned by **{owner_name}**"
            if obj:
                msg += " and" if not loc else ","

                msg += f" has object_id **{thrall['object_id']}**"
            if loc:
                ap = session.query(ActorPosition).filter_by(id=thrall['object_id']).first()
                tp = f"TeleportPlayer {round(ap.x)} {round(ap.y)} {ceil(ap.z)}" if ap else "unknown"
                msg += f" and is at location `{tp}`"
            msg += ".\n"

        return msg[:-1]

    @staticmethod
    async def get_thralls_string(arg, thralls, loc=False, obj=False):
        if not thralls or len(thralls) == 0:
            return f"**{arg}** has no thralls, pets or mounts."

        lines = []
        msg = f"Thralls, pets and mounts owned by **{arg}**:\n"
        for key in sorted(thralls):
            thrall = thralls[key]
            line = f"**{key}**"
            if obj:
                line += f" has object_id **{thrall['object_id']}**"
            if loc:
                if obj:
                    line += " and"
                ap = session.query(ActorPosition).filter_by(id=thrall['object_id']).first()
                tp = f"TeleportPlayer {round(ap.x)} {round(ap.y)} {ceil(ap.z)}" if ap else "unknown"
                line += f" is at location `{tp}`"
            lines.append(line)

        if len(lines) == 1:
            msg += lines[0]
        elif obj or loc:
            msg += ".\n".join(lines) + "."
        else:
            if len(lines) == 2:
                msg += " and ".join(lines)
            else:
                msg += ", ".join(lines[:-1]) + " and " + lines[-1] + "."

        return msg

    @command(name='roll', help="Rolls a dice in NdN format.")
    async def roll(self, ctx, *, Dice: str):
        result = await self.roll_dice(Dice)
        await ctx.send(f"{ctx.author.mention} rolled: " + result)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="getfuncomid", help="Checks if your FuncomID has been set.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def getfuncomid(self, ctx):
        disc_id = ctx.author.id
        disc_user = str(ctx.author)
        user = session.query(Users).filter_by(disc_id=disc_id).first()
        if user and user.funcom_id:
            await ctx.channel.send(f"Your FuncomID is currently set to {user.funcom_id}.")
        else:
            await ctx.channel.send(f"Your FuncomID has not been set yet. You can set it with `{PREFIX}setfuncomid <FuncomID>`")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="whois", help="Tells you the chararacter name(s) belonging to the given discord user or vice versa.")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whois(self, ctx, *, arg):
        disc_id = disc_user = user = None
        # try converting the given argument into a member
        member = await self.get_member(ctx, arg)
        if member:
            disc_id = member.id
            disc_user = str(member)
        # if conversion failed, check if the format looks like it's supposed to be a discord member
        else:
            if len(arg) > 5 and arg[-5] == '#':
                disc_user = arg
            elif len(arg) >= 17 and arg.isnumeric():
                disc_id = arg
            elif arg[:3] == "<@!" and arg[-1] == '>' and len(arg) == 22:
                disc_id = arg[3:-1]
        # try to determine the user
        users = []
        if disc_id:
            user = session.query(Users).filter_by(disc_id=disc_id).first()
            # update disc_user if conversion succeeded and disc_user is different than the one stored in Users
            if member and user and user.disc_user != str(member):
                user.disc_user = str(member)
                session.commit()
            users += [user] if user else []
        if not user and disc_user:
            user = session.query(Users).filter_by(disc_user=disc_user).first()
            if member and user and not user.disc_id:
                user.disc_id = disc_id
                session.commit()
            users += [user] if user else []
        if len(users) == 0:
            users = Users.get_users(arg)
        for user in Characters.get_users(arg):
            if not user in users:
                users += [user]
        await ctx.send(await self.get_user_string(arg, users, True))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="mychars", help="Check which chars have already been linked to your FuncomID.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def mychars(self, ctx):
        users = Users.get_users(ctx.author.id)
        if not users:
            await ctx.send("No characters linked to your discord account have been found. Have you been whitelisted already?")
            return
        # update disc_user if different than the one stored in Users
        user = users[0]
        if user.disc_user != str(ctx.author):
            user.disc_user = str(ctx.author)
            session.commit()
        await ctx.send(await self.get_user_string(str(ctx.author), users))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="clanmembers")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def clanmembers(self, ctx, *, arg):
        guilds = session.query(Guilds).filter(Guilds.name.like('%' + arg + '%')).all()
        guild_strings = await self.get_clan_string(arg, guilds)
        for msg in guild_strings:
            await ctx.send(msg)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="whoisowner")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whoisowner(self, ctx, *, arg):
        if arg == "":
            await ctx.send("Name is a required argument that is missing.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
            return

        loc = obj = strict = False

        arg_list = arg.split()
        if "loc" in arg_list:
            loc = True
            arg_list.remove("loc")
        if "obj" in arg_list:
            obj = True
            arg_list.remove("obj")
        if "strict" in arg_list:
            strict = True
            arg_list.remove("strict")
        name = " ".join(arg_list) if loc or obj or strict else arg

        thralls = Properties.get_thrall_owners(name=name, strict=strict)
        await ctx.send(await General.get_owner_string(name, thralls, loc, obj))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="isownedby")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def isownedby(self, ctx, *, arg):
        if arg == "":
            await ctx.send("Name or Id is a required argument that is missing.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
            return
        loc = obj = False

        arg_list = arg.split()
        if "loc" in arg_list:
            loc = True
            arg_list.remove("loc")
        if "obj" in arg_list:
            obj = True
            arg_list.remove("obj")

        name = " ".join(arg_list) if loc or obj else arg
        if name.isnumeric():
            owner_id = name
        else:
            fuzzy_name = "%" + name + "%"
            owners = [g for g in session.query(Guilds).filter(Guilds.name.like(fuzzy_name)).all()]
            if not owners:
                owners = [c for c in session.query(Characters).filter(Characters.name.like(fuzzy_name)).all()]
            if owners and len(owners) > 1:
                await ctx.send(f"Name **{name}** is ambiguous. Refine the filter or use owner_id.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
                return
            if not owners:
                if name.isnumeric():
                    await ctx.send(f"No owner with owner_id **{name}** has been found.")
                else:
                    await ctx.send(f"No owner with **{name}** in its name has been found.")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
                return
            owner = owners[0]

        thralls = Properties.get_thrall_owners(owner_id=owner.id)
        await ctx.send(await General.get_thralls_string(owner.name, thralls, loc, obj))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="reindex")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def reindex(self, ctx):
        roles = await General.get_guild_roles()

        # clan roles that are required based on the actual Characters table
        required_clan_roles = {}
        for char in session.query(Characters):
            if char.has_guild:
                guild_name = char.guild.name
                if guild_name in CLAN_IGNORE_LIST:
                    continue
                user = char.user
                if not user:
                    print(f"Couldn't find User for char {char.name} for clan roles indexing")
                    logger.info(f"Couldn't find User for char {char.name} for clan roles indexing")
                    continue
                disc_id = user.disc_id
                if not disc_id:
                    print(f"Couldn't find DiscordID for {char.name} for clan roles indexing")
                    logger.info(f"Couldn't find DiscordID for char {char.name} for clan roles indexing")
                    continue
                member = await self.get_member(ctx, disc_id)
                if not member:
                    print(f"Couldn't get member by DiscordID {disc_id} for {char.name} for clan roles indexing")
                    logger.info(f"Couldn't get member by DiscordID for {char.name} for clan roles indexing")
                    continue
                if not guild_name in required_clan_roles:
                    required_clan_roles[guild_name] = [member]
                else:
                    required_clan_roles[guild_name].append(member)

        # print("required_clan_roles:")
        # self.print_iter(required_clan_roles)

        # index roles by position
        roles_by_pos = {}
        for name, role in roles.items():
            roles_by_pos[role.position] = role

        # print("roles_by_pos:")
        # self.print_iter(roles_by_pos)

        roles_idx = []
        for pos in sorted(roles_by_pos):
            name = roles_by_pos[pos].name
            if name == CLAN_START_ROLE:
                start_pos = len(roles_idx)
            elif name == CLAN_END_ROLE:
                end_pos = len(roles_idx)
            roles_idx.append(name)

        # print("roles_idx:")
        # self.print_iter(roles_idx)

        before_clan_roles = roles_idx[:end_pos+1]
        after_clan_roles = roles_idx[start_pos:]

        # print("before_clan_roles:")
        # self.print_iter(before_clan_roles)
        # print("after_clan_roles:")
        # self.print_iter(after_clan_roles)

        # create a slice of only those guilds that are actually required
        clan_roles = []
        for name in sorted(roles_idx[end_pos+1:start_pos]):
            # remove existing roles that are no longer required
            if not name in required_clan_roles:
                await roles[name].delete()
                del roles[name]
            # create the slice of existing clans otherwise
            else:
                clan_roles.append(name)

        # print("clan_roles:")
        # self.print_iter(clan_roles)

        # add roles and update their members as required
        for name, members in required_clan_roles.items():
            # add clan roles not existing yet
            if not name in roles:
                clan_roles.append(name)
                hoist = CLAN_ROLE_HOIST
                mentionable = CLAN_ROLE_MENTIONABLE
                roles[name] = await saved.GUILD.create_role(name=name, hoist=hoist, mentionable=mentionable)
                # add all members to that role
                for member in members:
                    await member.add_roles(roles[name])
            # update existing roles
            else:
                # add members not alread assigned to the role
                for member in members:
                    if not member in roles[name].members:
                        await member.add_roles(roles[name])
                # remove members that are assigned to the role but shouldn't be
                for member in roles[name].members:
                    if not member in members:
                        await member.remove_roles(roles[name])

        # create a positions list for the roles
        reindexed_roles = before_clan_roles + sorted(clan_roles, reverse=True) + after_clan_roles
        positions = {}
        for position in range(1, len(reindexed_roles)):
            name = reindexed_roles[position]
            positions[roles[name]] = position

        # print("positions:")
        # self.print_iter(positions)

        await saved.GUILD.edit_role_positions(positions)
        await ctx.send(f"Done!")

def setup(bot):
    bot.add_cog(General(bot))

class Die:
    def __init__(self, num=1, sides=1, sign=1):
        self.num = num
        self.sides = sides
        self.sign = sign

    def __repr__(self):
        return f"<Die(num={self.num}, sides={self.sides}, sign={self.sign})>"

    @property
    def sign(self):
        return self._sign

    @sign.setter
    def sign(self, value):
        if type(value) is str:
            if value == "+":
                self._sign = 1
            elif value == "-":
                self._sign = -1
        elif type(value) is int:
            if value >= 0:
                self._sign = 1
            else:
                self._sign = -1

    @property
    def num(self):
        return self._num

    @num.setter
    def num(self, value):
        if type(value) is int:
            if value > 0:
                self._num = value

    @property
    def sides(self):
        return self._sides

    @sides.setter
    def sides(self, value):
        if type(value) is int:
            if value > 0:
                self._sides = value

    def roll(self):
        sum = 0
        for i in range(self._num):
            sum += random.randint(1, self._sides)
        return sum * self._sign

class Dice(list):
    def roll(self):
        sum = 0
        results = []
        for d in self:
            r = d.roll()
            results.append(r)
            sum += r
        return (results, sum)

    def __repr__(self):
        repr = "<Dice("
        idx = 0
        for d in self:
            repr += f"die{idx}={'-' if d.sign < 0 else ''}{d.num}d{d.sides}, "
            idx += 1
        return repr[:-2] + ")>"
