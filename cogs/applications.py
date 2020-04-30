from discord import Member
from discord.ext import commands
from discord.ext.commands import command
from datetime import datetime
import config as cfg
from logger import logger
from checks import is_not_applicant, is_applicant, has_role
from exceptions import NotNumberError, NumberNotInRangeError
from google_api import sheets
from helpers import *

class Applications(commands.Cog, name="Application commands"):
    def __init__(self, bot):
        self.bot = bot

    @command(name='apply', help="Starts the application process")
    @is_not_applicant()
    async def apply(self, ctx):
        await ctx.author.create_dm()
        await send_question(ctx.author, 0, msg=parse(ctx.author, cfg.APPLIED))
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{ctx.author} has started an application.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")
        cfg.APL[ctx.author] = \
            {'timestamp': datetime.utcnow(), 'finished': False, 'open': True, 'questionId': 0, 'answers': {}}

    @command(name='question', help="Used to switch to a given question. If no number is given, repeats the current question")
    @is_applicant()
    @commands.dm_only()
    async def question(self, ctx, Number=None):
        if not cfg.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, cfg.APP_CLOSED))
            return
        if Number is None:
            if cfg.APL[ctx.author]['questionId'] < 0:
                await ctx.author.dm_channel.send(parse(ctx.author, cfg.FINISHED))
                return
            await send_question(ctx.author, cfg.APL[ctx.author]['questionId'])
            return
        if not Number.isnumeric():
            raise NotNumberError(f"Argument must be a number between 1 and {len(cfg.QUESTIONS)}.")
        if not Number.isnumeric() or int(Number) < 1 or int(Number) > len(cfg.QUESTIONS):
            raise NumberNotInRangeError(f"Number must be between 1 and {len(cfg.QUESTIONS)}.")
        await send_question(ctx.author, int(Number) - 1)
        cfg.APL[ctx.author]['questionId'] = int(Number) - 1

    @command(name='overview', help="Display all questions that have already been answered")
    @is_applicant()
    async def overview(self, ctx):
        await send_overview(ctx.author)

    @command(name='submit', help="Submit your application and send it to the admins")
    @is_applicant()
    async def submit(self, ctx):
        if len(cfg.QUESTIONS) > len(cfg.APL[ctx.author]['answers']):
            await ctx.author.dm_channel.send("Please answer all questions first.")
            return
        if not cfg.APL[ctx.author]['open']:
            await ctx.author.dm_channel.send(parse(ctx.author, cfg.APP_CLOSED))
            return
        cfg.APL[ctx.author]['open'] = False
        await ctx.author.dm_channel.send(parse(ctx.author, cfg.COMMITED))
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        msg = f"{ctx.author} has filled out the application. You can now either \n`{cfg.PREFIX}accept <applicant> <message>`, `{cfg.PREFIX}reject <applicant> <message>` or `{cfg.PREFIX}review <applicant> <message>` (asking the Applicant to review their answers) it.\nIf <message> is omitted a default message will be sent.\nIf <applicant> is also omitted, it will try to target the last application."
        await send_overview(ctx.author, msg=msg, submitted=True)

    @command(name='cancel', help="Cancel your application")
    @is_applicant()
    async def cancel(self, ctx):
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{ctx.author} has canceled their application.")
        await ctx.author.dm_channel.send("Your application has been canceled.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")
        del cfg.APL[ctx.author]

    @command(name='accept', help="Accept the application. If message is ommitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def accept(self, ctx, Applicant=None, *Message):
        # if no Applicant is given, try to automatically determine one
        if Applicant is None:
            Applicant = await find_last_Applicant(ctx, self.bot.user)
            if Applicant is None:
                await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}accept <applicant>`.")
                return
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        # confirm that there is a closed application for that Applicant
        if not Applicant in cfg.APL or cfg.APL[Applicant]['open']:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {Applicant}. Please verify that the name is written correctly and try again.")
        # remove Not Applied role
        if Message:
            Message = " ".join(Message)
        if cfg.ROLE[cfg.NOT_APPLIED_ROLE] in Applicant.roles:
            new_roles = Applicant.roles
            new_roles.remove(cfg.ROLE[cfg.NOT_APPLIED_ROLE])
            await Applicant.edit(roles=new_roles)

        # Whitelist Applicant
        SteamID64 = find_steamID64(Applicant)
        if SteamID64:
            result = await whitelist_player(ctx, SteamID64, Applicant)
        else:
            result = "NoSteamIDinAnswer"

        # Send feedback about accepting the application
        if not Message:
            Message = parse(ctx.author, cfg.ACCEPTED)
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{Applicant}'s application has been accepted.")
        await Applicant.dm_channel.send("Your application was accepted:\n" + Message)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been accepted.")

        # Send feedback about whitelisting success
        info = parse(ctx.author, "They have been informed to request whitelisting in {SUPPORT-REQUESTS}.")
        if result == "NoSteamIDinAnswer":
            await Applicant.dm_channel.send("Whitelisting failed, you have given no valid SteamID64 your answer. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {Applicant} failed. No valid SteamID64 found in answer:\n> {cfg.APL[ctx.author]['answers'][cfg.STEAMID_QUESTION]}\n{info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
        elif result == "IsGabesIDError" :
            await Applicant.dm_channel.send("Whitelisting failed, you have given the example SteamID64 of Gabe Newell instead of your own. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {Applicant} failed. Applicant gave Gabe Newells SteamID64. {info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. IsGabesIDError")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. IsGabesIDError")
        elif result.find("FailedError") >= 0:
            result = result[12:]
            await Applicant.dm_channel.send("Whitelisting failed. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {Applicant} failed (error message: {result}). {info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
        else:
            await Applicant.dm_channel.send(parse(ctx.author, cfg.WHITELISTING_SUCCEEDED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(result)
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")

        # remove application from list of open applications
        del cfg.APL[Applicant]
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been accepted.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been accepted.")

    @command(name='reject', help="Reject the application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def reject(self, ctx, Applicant=None, *Message):
        # if no Applicant is given, try to automatically determine one
        if Applicant is None:
            Applicant = await find_last_Applicant(ctx, self.bot.user)
            if Applicant is None:
                cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}reject <applicant> <message>`.")
                return
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        # confirm that there is a closed application for that Applicant
        if not Applicant in cfg.APL or cfg.APL[Applicant]['open']:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {Applicant}. Please verify that the name is written correctly and try again.")
        # Send feedback to applications channel and to Applicant
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{Applicant}'s application has been rejected.")
        if not Message:
            await Applicant.dm_channel.send(parse(ctx.author, "Your application was rejected:\n" + cfg.REJECTED))
        else:
            await Applicant.dm_channel.send("Your application was rejected:\n" + " ".join(Message))
        # remove application from list of open applications
        del cfg.APL[Applicant]
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been rejected.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been rejected.")

    @command(name='review', help="Ask the Applicant to review their application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def review(self, ctx, Applicant=None, *Message):
        # if no Applicant is given, try to automatically determine one
        if Applicant is None:
            Applicant = await find_last_Applicant(ctx, self.bot.user)
            if Applicant is None:
                await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}review <applicant> <message>`.")
                return
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        # confirm that there is a closed application for that Applicant
        if not Applicant in cfg.APL or cfg.APL[Applicant]['open']:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {Applicant}. Please verify that the name is written correctly and try again.")
            return
        # Send feedback to applications channel and to Applicant
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{Applicant}'s application has been returned.")
        explanation = f"\nYou can change the answer to any question by going to that question with `{cfg.PREFIX}question <number>` and then writing your new answer.\nYou can always review your current answers by entering `{cfg.PREFIX}overview`."
        if not Message:
            await send_overview(Applicant, "Your application was returned to you for review:\n" + cfg.REVIEWED + explanation)
        else:
            await send_overview(Applicant, "Your application was returned to you for review:\n" + " ".join(Message) + explanation)
        # remove application from list of open applications
        cfg.APL[Applicant]['open'] = True
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been returned for review.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been returned for review.")

    @command(name='showapp', help="Displays the given Applicants application if it has been submitted. When Applicant is omitted, shows all applications.")
    @has_role(cfg.ADMIN_ROLE)
    async def showapp(self, ctx, *, Applicant=None):
        if Applicant:
            Applicant = await commands.MemberConverter().convert(ctx, Applicant)
            if not Applicant in cfg.APL:
                await ctx.channel.send(f"No application for {Applicant} found")
            elif cfg.APL[Applicant]['open']:
                await ctx.channel.send("Can't access application while it's still being worked on.")
            else:
                await send_overview(ctx.author, submitted=True)
            return
        else:
            msg = "" if len(cfg.APL) > 0 else "No open applications right now."
            for Applicant, aplication in cfg.APL.items():
                msg += f"Applicant {Applicant} is {'still working on their application' if aplication['open'] else 'waiting for admin approval'}.\n"
            if len(cfg.APL) > 0:
                msg += f"You can view a specific application by entering `{cfg.PREFIX}showapp <applicant>`."
            await ctx.channel.send(msg)
            return

    @command(name='cancelapp', help="Displays the given Applicants application if it has been submitted. When Applicant is omitted, shows all applications.")
    @has_role(cfg.ADMIN_ROLE)
    async def cancelapp(self, ctx, Applicant, *Message):
        Applicant = await commands.MemberConverter().convert(ctx, Applicant)
        if not Applicant in cfg.APL:
            await ctx.channel.send(f"Applicant {Applicant} couldn't be found.")
            return
        del cfg.APL[Applicant]
        if Message:
            Message = " ".join(Message)
        await ctx.channel.send(f"Application for {Applicant} has been cancelled.")
        await Applicant.dm_channel.send(f"Your application was cancelled by an administrator.{' Message: ' + Message + '.' if len(Message) > 0 else ''}")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been cancelled.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {Applicant}'s application has been cancelled.")

    @command(name='reloadsheets', help="Updates all default messages and questions from google sheets.")
    @has_role(cfg.ADMIN_ROLE)
    async def reloadsheets(self, ctx):
        update_questions()
        await ctx.channel.send("Default messages and questions have been reloaded from google sheets.")
        logger.info("Default messages and questions have been reloaded from google sheets.")

def setup(bot):
    bot.add_cog(Applications(bot))
