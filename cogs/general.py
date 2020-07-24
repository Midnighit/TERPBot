import random
from discord.ext import commands
from discord.ext.commands import command
from logger import logger
from exiles_api import *
from config import *
from exceptions import *
from checks import *

class General(commands.Cog, name="General commands"):
    def __init__(self, bot):
        self.bot = bot

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
    async def get_user_string(arg, users):
        if not users:
            return f"No discord user or chracter named {arg} was found."
        msg = ''
        for user in users:
            msg += f"The characters belonging to the discord nick **{user.disc_user}** are:\n"
            for char in user.characters:
                lldate = char.last_login.strftime("%d-%b-%Y %H:%M:%S UTC")
                if char.slot == 'active':
                    msg += f"**{char.name}** on **active** slot (last login: {lldate})\n"
                else:
                    msg += f"**{char.name}** on slot **{char.slot}** (last login: {lldate})\n"
            msg += '\n'
        return msg[:-2]

    @command(name='roll', help="Rolls a dice in NdN format")
    async def roll(self, ctx, *, Dice: str):
        result = await self.roll_dice(Dice)
        await ctx.send(f"{ctx.author.mention} rolled: " + result)

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
        logger.info(f"Player {ctx.author} set read their FuncomID.")

    @command(name="whois", help="Tells you the chararacter name(s) belonging to the given discord user or vice versa")
    @has_role_greater_or_equal(SUPPORT_ROLE)
    async def whois(self, ctx, *, arg):
        disc_id = disc_user = None
        # try converting the given argument into a member
        member = await self.get_member(ctx, arg)
        if member:
            disc_id = member.id
            disc_user = str(member)
        # if conversion failed, check if the format looks like it's supposed to be a discord member
        else:
            if len(arg) > 5 and arg[-5] == '#':
                disc_user = arg
            elif len(arg) == 18 and arg.isnumeric():
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
        if len(users) == 0:
            users = Characters.get_users(arg)
        await ctx.send(await self.get_user_string(arg, users))
        logger.info(f"Player {ctx.author} used the whois command for {arg}.")

    @command(name="mychars", help="Check which chars have already been linked to your FuncomID.")
    @has_not_role(NOT_APPLIED_ROLE)
    async def mychars(self, ctx):
        users = Users.get_users(ctx.author.id)
        # update disc_user if different than the one stored in Users
        user = users[0]
        if user.disc_user != str(ctx.author):
            user.disc_user = str(ctx.author)
            session.commit()
        await ctx.send(await self.get_user_string(str(ctx.author), users))
        logger.info(f"Player {ctx.author} used mychars command.")

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
