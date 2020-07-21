import config as saved
from config import *
from exceptions import *
from discord.ext.commands import check, BadArgument, MissingRequiredArgument
from exiles_api import session, Applications

##############
''' Checks '''
##############

def is_applicant():
    async def predicate(ctx):
        if not session.query(Applications).filter_by(disc_id=ctx.author.id).first():
            raise NotApplicantError()
        return True
    return check(predicate)

def is_not_applicant():
    async def predicate(ctx):
        if app := session.query(Applications).filter_by(disc_id=ctx.author.id).first():
            if app.status == 'accepted':
                raise MemberError()
            else:
                raise ApplicantError()
        return True
    return check(predicate)

def is_not_bot():
    async def predicate(ctx):
        if ctx.author == bot.user:
            raise IsBotError()
        return True
    return check(predicate)

def has_not_role(check_role: str):
    async def predicate(ctx):
        member = saved.GUILD.get_member(ctx.author.id)
        if saved.ROLE[check_role] in member.roles:
            raise HasRoleError(f"Command may not used by users with role {check_role}.")
        return True
    return check(predicate)

def has_role(check_role: str):
    async def predicate(ctx):
        member = saved.GUILD.get_member(ctx.author.id)
        if not saved.ROLE[check_role] in member.roles:
            raise HasNotRoleError(f"Command may only be used by users with role {check_role}.")
        return True
    return check(predicate)

def has_role_greater_or_equal(check_role: str):
    async def predicate(ctx):
        member = saved.GUILD.get_member(ctx.author.id)
        for author_role in member.roles:
            if author_role >= saved.ROLE[check_role]:
                return True
        raise RoleTooLowError(f"Command may only be used by users with role greater or equal than {check_role}.")
    return check(predicate)

def has_role_greater(check_role: str):
    async def predicate(ctx):
        member = saved.GUILD.get_member(ctx.author.id)
        for author_role in member.roles:
            if author_role > saved.ROLE[check_role]:
                return True
        raise RoleTooLowError(f"Command may only be used by users with role greater than {check_role}.")
    return check(predicate)

def number_in_range(min: int, max: int):
    async def predicate(ctx):
        if ctx.message.content.lstrip().find(' ') > 0:
            v = ctx.message.content.split()
        else:
            raise MissingRequiredArgument(ctx.command)
        if not v[1].isnumeric():
            raise NotNumberError(f"Command requires a number between {str(min)} and {str(max)} as argument.")
        if int(v[1]) < min or int(v[1]) > max:
            raise NumberNotInRangeError(f"Number must be between {str(min)} and {str(max)}.")
        return True
    return check(predicate)
