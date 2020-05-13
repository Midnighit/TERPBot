import exceptions as exc
import config as cfg
from db import sessionSupp, Apps
from discord.ext.commands import check, BadArgument, MissingRequiredArgument

##############
''' Checks '''
##############

def is_applicant():
    async def predicate(ctx):
        if not sessionSupp.query(Apps).filter_by(applicant=str(ctx.author)).first():
            raise exc.NotApplicantError()
        return True
    return check(predicate)

def is_not_applicant():
    async def predicate(ctx):
        if sessionSupp.query(Apps).filter_by(applicant=str(ctx.author)).first():
            raise exc.ApplicantError()
        return True
    return check(predicate)

def is_not_bot():
    async def predicate(ctx):
        if ctx.author == bot.user:
            raise exc.IsBotError()
        return True
    return check(predicate)

def has_not_role(check_role: str):
    async def predicate(ctx):
        member = cfg.GUILD.get_member(ctx.author.id)
        if cfg.ROLE[check_role] in member.roles:
            raise HasRoleError(f"Command may not used by users with role {check_role}.")
        return True
    return check(predicate)

def has_role(check_role: str):
    async def predicate(ctx):
        member = cfg.GUILD.get_member(ctx.author.id)
        if not cfg.ROLE[check_role] in member.roles:
            raise exc.HasNotRoleError(f"Command may only be used by users with role {check_role}.")
        return True
    return check(predicate)

def has_role_greater_or_equal(check_role: str):
    async def predicate(ctx):
        member = cfg.GUILD.get_member(ctx.author.id)
        for author_role in member.roles:
            if author_role >= cfg.ROLE[check_role]:
                return True
        raise RoleTooLowError(f"Command may only be used by users with role greater or equal than {check_role}.")
    return check(predicate)

def has_role_greater(check_role: str):
    async def predicate(ctx):
        member = cfg.GUILD.get_member(ctx.author.id)
        for author_role in member.roles:
            if author_role > cfg.ROLE[check_role]:
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
            raise exc.NotNumberError(f"Command requires a number between {str(min)} and {str(max)} as argument.")
        if int(v[1]) < min or int(v[1]) > max:
            raise exc.NumberNotInRangeError(f"Number must be between {str(min)} and {str(max)}.")
        return True
    return check(predicate)
