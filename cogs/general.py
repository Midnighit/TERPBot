import random
from math import ceil
from discord.ext import commands
from discord.ext.commands import command
from logger import logger
from checks import has_not_role, has_role_greater_or_equal
from config import (
    NOT_APPLIED_ROLE, PREFIX, SUPPORT_ROLE,
    CLAN_IGNORE_LIST, CLAN_START_ROLE, CLAN_END_ROLE, CLAN_ROLE_HOIST, CLAN_ROLE_MENTIONABLE
)
from exiles_api import RANKS, session, ActorPosition, Users, Owner, Properties, Characters, Guilds
from exceptions import NoDiceFormatError
from functions import get_guild, get_roles, get_member, split_message, get_channels

whois_help = "Tells you the chararacter name(s) belonging to the given discord user or vice versa."


class General(commands.Cog, name="General commands."):
    def __init__(self, bot):
        self.bot = bot
        self.guild = get_guild(bot)

    @staticmethod
    def print_iter(iter):
        if isinstance(iter, dict):
            print("{")
            for k, v in iter.items():
                print(f"    {k}: {v},")
            print("}")
        elif isinstance(iter, list):
            print("[")
            for idx in range(len(iter)):
                print(f"    {idx}: {iter[idx]},")
            print("]")

    @staticmethod
    async def roll_dice(input):
        def rreplace(s, old, new, occurrence):
            li = s.rsplit(old, occurrence)
            return new.join(li)

        if input.find("d") == -1:
            raise NoDiceFormatError()
        input = input.replace(" ", "")
        dice = Dice()
        num = ""
        type = "s"
        sign = "+"
        val = 0
        d = None
        for c in input:
            if c in ("+", "-"):
                if type == "s" and num != "":
                    val = val - int(num) if sign == "-" else val + int(num)
                elif type == "s" and num == "":
                    pass
                elif num != "":
                    d.sides = int(num)
                    d.sign = sign
                    dice.append(d)
                else:
                    raise NoDiceFormatError()
                num = ""
                type = "s"
                sign = c
            elif c == "d":
                d = Die(num=int(num)) if num != "" else Die()
                num = ""
                type = "d"
            else:
                if not c.isnumeric():
                    raise NoDiceFormatError()
                num += c
        if type == "s" and num != "":
            val = val - int(num) if sign == "-" else val + int(num)
        elif num != "":
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
    async def get_user_string(arg, users, detailed=True, with_char_id=False, with_disc_id=False):
        if not users:
            return f"No discord user or character named **{arg}** was found."

        msg = ""
        for user in users:
            disc_id = "(@" + user.disc_id + ") " if with_disc_id else ""
            if len(user.characters) == 0:
                msg += f"No characters linked to discord nick **{user.disc_user}** {disc_id}have been found.\n\n"
            else:
                msg += f"The characters belonging to the discord nick **{user.disc_user}** {disc_id}are:\n"
                if detailed:
                    for char in user.characters:
                        char_id = " (" + str(char.id) + ")" if with_char_id else ""
                        lldate = char.last_login.strftime("%d-%b-%Y %H:%M UTC")
                        guild = f" is **{RANKS[char.rank]}** of clan **{char.guild.name}**" if char.has_guild else ""
                        slot = " on **active** slot" if char.slot == "active" else f" on slot **{char.slot}**"
                        msg += f"**{char.name}**{char_id}{guild}{slot} (last login: {lldate})\n"
                else:
                    char_names = [char.name for char in user.characters]
                    if len(char_names) > 2:
                        csv = "**, **".join(char_names[:-2])
                        asv = "** and **".join(char_names[-2:])
                        msg += "**" + csv + "**, **" + asv + "**\n"
                    elif len(char_names) == 2:
                        msg += "**" + char_names[0] + "** and **" + char_names[1] + "**\n"
                    else:
                        msg += "**" + char_names[0] + "**\n"
                msg += "\n"
        return msg[:-2]

    @staticmethod
    async def get_clan_string(arg, guilds, guild_id=None, char_id=None):
        if not guilds:
            return [f"No clan named **{arg}** was found."]

        msg = []
        chunk = ""
        for guild in guilds:
            members = guild.members
            mem = "members" if len(members) > 1 or len(members) == 0 else "member"
            gid = f"({guild.id}) " if guild_id else ""
            chunk += f"Clan **{guild.name}** {gid}has **{len(members)}** {mem}:\n"
            if len(members) == 0:
                continue
            members_by_rank = {}
            for member in members:
                rank = 3 if member.rank > 3 else member.rank
                if rank is None:
                    rank = -1
                if rank not in members_by_rank:
                    members_by_rank[member.rank] = [member]
                else:
                    members_by_rank[member.rank] += [member]
            for rank in range(3, -2, -1):
                if rank not in members_by_rank:
                    continue
                members = members_by_rank[rank]
                rank_nam = "Undeterminable rank" if rank == -1 else RANKS[rank]
                for member in members:
                    mem_msg = ""
                    lldate = member.last_login.strftime("%d-%b-%Y %H:%M UTC")
                    cid = f"({member.id}) " if char_id else ""
                    slot = member.slot
                    if slot == "active":
                        mem_msg += (
                            f"**{member.name}** {cid}is **{rank_nam}** on " f"**active** slot (last login: {lldate})\n"
                        )
                    else:
                        mem_msg += (
                            f"**{member.name}** {cid}is **{rank_nam}** on " f"slot **{slot}** (last login: {lldate})\n"
                        )

                    if len(chunk) + len(mem_msg) >= 2000:
                        msg.append(chunk)
                        chunk = mem_msg
                    else:
                        chunk += mem_msg
            if len(chunk) >= 1998:
                msg.append(chunk)
                chunk = "\n"
            else:
                chunk += "\n"

        msg.append(chunk)
        return msg

    @staticmethod
    async def get_owner_string(arg, thralls, loc=False, obj=False):
        if not thralls or len(thralls) == 0:
            return f"No thralls, pets or mounts with **{arg}** in their name were found."

        msg = f"Thralls, pets and mounts with **{arg}** in their name:\n"
        for key in sorted(thralls):
            thrall = thralls[key]
            owner_name = thrall["owner"].name if thrall["owner"] else "nobody"
            if owner_name == "":
                owner_name = "no name"
            msg += f"**{key}** is owned by **{owner_name}**"
            if obj:
                msg += " and" if not loc else ","

                msg += f" has object_id **{thrall['object_id']}**"
            if loc:
                ap = session.query(ActorPosition).filter_by(id=thrall["object_id"]).first()
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
                ap = session.query(ActorPosition).filter_by(id=thrall["object_id"]).first()
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

    @command(name="roll", help="Rolls a dice in NdN format.")
    async def roll(self, ctx, *, Dice: str):
        result = await self.roll_dice(Dice)
        await ctx.send(f"{ctx.author.mention} rolled: " + result)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="getfuncomid", help="Checks if your FuncomID has been set.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def getfuncomid(self, ctx):
        disc_id = ctx.author.id
        user = session.query(Users).filter_by(disc_id=disc_id).first()
        if user and user.funcom_id:
            await ctx.channel.send(f"Your FuncomID is currently set to {user.funcom_id}.")
        else:
            await ctx.channel.send(
                f"Your FuncomID has not been set yet. You can set it with `{PREFIX}setfuncomid <FuncomID>`"
            )
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="whois", aliases=["whomst", "whomstthefuck"], help=whois_help)
    async def whois(self, ctx, *, Name):
        def is_staff():
            roles = get_roles(self.guild)
            member = self.guild.get_member(ctx.author.id)
            for author_role in member.roles:
                if author_role >= roles[SUPPORT_ROLE]:
                    return True

        disc_id = disc_user = user = show_char_id = show_disc_id = None
        arg_list = Name.split()
        if "char_id" in arg_list:
            show_char_id = True
            arg_list.remove("char_id")
        if "disc_id" in arg_list:
            show_disc_id = True
            arg_list.remove("disc_id")
        arg = " ".join(arg_list)
        # try converting the given argument into a member
        member = await get_member(ctx, arg)
        if member:
            disc_id = member.id
            disc_user = str(member)
        # if conversion failed, check if the format looks like it's supposed to be a discord member
        else:
            if len(arg) > 5 and arg[-5] == "#":
                disc_user = arg
            elif len(arg) >= 17 and arg.isnumeric():
                disc_id = arg
            elif arg[:3] == "<@!" and arg[-1] == ">" and len(arg) == 22:
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
            if user not in users:
                users += [user]
        detailed = True if is_staff() else False
        await ctx.send(await self.get_user_string(arg, users, detailed, show_char_id, show_disc_id))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="hasmoney", help="Gives the amount of Pippi money in the wallet of the given character.")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def hasmoney(self, ctx, *, Name):
        if Name.isnumeric():
            owner = Owner.get(Name)
            owners = [owner]
        else:
            owners = Owner.get_by_name(Name, strict=False, nocase=True)
            money = Properties.get_pippi_money(name=Name)

        if len(owners) == 0:
            msg = f"No character or clan named **{Name}** was found."
        else:
            m = []
            for owner in owners:
                if owner.is_character:
                    money = Properties.get_pippi_money(char_id=owner.id)
                else:
                    money = Properties.get_pippi_money(guild_id=owner.id)
                gold, silver, bronze = money
                m.append(f"**{owner.name}** has **{gold}** gold, **{silver}** silver and **{bronze}** bronze.")

            msg = "\n".join(m)

        for part in split_message(msg):
            await ctx.send(part)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="mychars", help="Check which chars have already been linked to your FuncomID.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def mychars(self, ctx):
        users = Users.get_users(ctx.author.id)
        if not users:
            await ctx.send(
                "No characters linked to your discord account have been found. Have you been whitelisted already?"
            )
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
        guild_id = char_id = False
        arg_list = arg.split()
        if "guild_id" in arg_list:
            guild_id = True
            arg_list.remove("guild_id")
        if "char_id" in arg_list:
            char_id = True
            arg_list.remove("char_id")
        name = " ".join(arg_list)
        if name == "":
            await ctx.send("Name is a required argument that is missing.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
            return

        guilds = session.query(Guilds).filter(Guilds.name.like("%" + name + "%")).all()
        guild_strings = await self.get_clan_string(name, guilds, guild_id, char_id)
        for msg in guild_strings:
            await ctx.send(msg)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="whoisowner")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whoisowner(self, ctx, *, arg):
        loc = obj = strict = False
        arg_list = arg.split()
        if "loc" in arg_list:
            loc = True
            arg_list.remove("loc")
        if "obj_id" in arg_list:
            obj = True
            arg_list.remove("obj_id")
        if "strict" in arg_list:
            strict = True
            arg_list.remove("strict")
        name = " ".join(arg_list)
        if name == "":
            await ctx.send("Name is a required argument that is missing.")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")
            return

        thralls = Properties.get_thrall_owners(name=name, strict=strict)
        await ctx.send(await self.get_owner_string(name, thralls, loc, obj))
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
        if "obj_id" in arg_list:
            obj = True
            arg_list.remove("obj_id")

        name = " ".join(arg_list) if loc or obj else arg
        if name.isnumeric():
            owner = session.query(Guilds).get(name)
            if not owner:
                owner = session.query(Characters).get(name)
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
        await ctx.send(await self.get_thralls_string(owner.name, thralls, loc, obj))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @command(name="reindex")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def reindex(self, ctx):
        roles = get_roles(self.guild)

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
                member = await get_member(ctx, disc_id)
                if not member:
                    print(f"Couldn't get member by DiscordID {disc_id} for {char.name} for clan roles indexing")
                    logger.info(f"Couldn't get member by DiscordID for {char.name} for clan roles indexing")
                    continue
                if guild_name not in required_clan_roles:
                    required_clan_roles[guild_name] = [member]
                else:
                    required_clan_roles[guild_name].append(member)

        # index roles by position
        roles_by_pos = {}
        for name, role in roles.items():
            roles_by_pos[role.position] = role

        roles_idx = []
        for pos in sorted(roles_by_pos):
            name = roles_by_pos[pos].name
            if name == CLAN_START_ROLE:
                start_pos = len(roles_idx)
            elif name == CLAN_END_ROLE:
                end_pos = len(roles_idx)
            roles_idx.append(name)

        before_clan_roles = roles_idx[: end_pos + 1]
        after_clan_roles = roles_idx[start_pos:]

        # create a slice of only those guilds that are actually required
        clan_roles = []
        for name in sorted(roles_idx[end_pos + 1:start_pos]):
            # remove existing roles that are no longer required
            if name not in required_clan_roles:
                await roles[name].delete()
                del roles[name]
            # create the slice of existing clans otherwise
            else:
                clan_roles.append(name)

        # add roles and update their members as required
        for name, members in required_clan_roles.items():
            # add clan roles not existing yet
            if name not in roles:
                clan_roles.append(name)
                hoist = CLAN_ROLE_HOIST
                mentionable = CLAN_ROLE_MENTIONABLE
                roles[name] = await self.guild.create_role(name=name, hoist=hoist, mentionable=mentionable)
                # add all members to that role
                for member in members:
                    await member.add_roles(roles[name])
            # update existing roles
            else:
                # add members not alread assigned to the role
                for member in members:
                    if member not in roles[name].members:
                        await member.add_roles(roles[name])
                # remove members that are assigned to the role but shouldn't be
                for member in roles[name].members:
                    if member not in members:
                        await member.remove_roles(roles[name])

        # create a positions list for the roles
        reindexed_roles = before_clan_roles + sorted(clan_roles, reverse=True) + after_clan_roles
        positions = {}
        for position in range(1, len(reindexed_roles)):
            name = reindexed_roles[position]
            positions[roles[name]] = position

        # print("positions:")
        # self.print_iter(positions)

        await self.guild.edit_role_positions(positions)
        await ctx.send("Done!")

    @command(name="donate", aliases=["donations", "donation"])
    async def donate(self, ctx):
        channels = get_channels(bot=self.bot)
        donations_channel = channels["donations"] if "donations" in channels else None
        ari = await get_member(ctx, 123298178828206080)
        if donations_channel and ari:
            await ctx.send(
                f"If you'd like to contribute to the operating costs of the server, please have a look at "
                f"{donations_channel.mention}. You can either contribute monthly through the Patreon, "
                f"or make a one time donation through PayPal. You aren't obligated to pay, but either way "
                f"it helps keep the server up and running at less of an expense to {ari.mention}"
            )
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")


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
        if isinstance(value, str):
            if value == "+":
                self._sign = 1
            elif value == "-":
                self._sign = -1
        elif isinstance(value, int):
            if value >= 0:
                self._sign = 1
            else:
                self._sign = -1

    @property
    def num(self):
        return self._num

    @num.setter
    def num(self, value):
        if isinstance(value, int):
            if value > 0:
                self._num = value

    @property
    def sides(self):
        return self._sides

    @sides.setter
    def sides(self, value):
        if isinstance(value, int):
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
