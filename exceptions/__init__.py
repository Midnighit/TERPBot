from discord.ext import commands as cmds


##############
''' Exceptions '''
##############

class CustomError(cmds.CommandError):
    pass

class IsBotError(CustomError):
    pass

class ConversionError(CustomError):
    def __init__(self, msg="Couldn't determine discord user account."):
        super().__init__(msg)

class NotApplicantError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Command may not be used when there is no application."
        super().__init__(msg)

class ApplicantError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Command may not be used when there already is an application."
        super().__init__(msg)

class MemberError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Command may not be used when user already has been accepted."
        super().__init__(msg)

class NotPrivateError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Command may only be used in private messages."
        super().__init__(msg)

class HasRoleError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "User has role that prevents using this command."
        super().__init__(msg)

class HasNotRoleError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "User doesn't have required role for this command."
        super().__init__(msg)

class RoleTooLowError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Role to low to execute this command."
        super().__init__(msg)

class NotFuncomIdError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "FuncomID must be at least 10 characters long and may only contain the letters a-f and digits."
        super().__init__(msg)

class NotNumberError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Argument must be a number."
        super().__init__(msg)

class NumberNotInRangeError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Number is not within allowed range."
        super().__init__(msg)

class RConConnectionError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "No RCon connection could be made. Please try again later."
        super().__init__(msg)

class NoDiceFormatError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Dice conversion error. Dice need to be in NdM+X format (e.g. 3d6+5)"
        super().__init__(msg)
