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
            msg = "Command may not be used without an open application."
        super().__init__(msg)

class ApplicantError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Command may not be used with an open application."
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

class NotSteamIdError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "SteamID64 must be a 17 digits number."
        super().__init__(msg)

class IsGabesIDError(CustomError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "This is Gabe Newell's SteamID64. You probably got it as an example of how a SteamID64 is supposed to look like. Please try again with the correct SteamID."
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
