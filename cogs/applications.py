from discord.ext import commands
from discord.ext.commands import command
from datetime import datetime
import config as cfg
from logger import logger
from google_api import sheets
from db import sessionSupp, Apps
from exceptions import *
from checks import *
from helpers import *

class Applications(commands.Cog, name="Application commands"):
    def __init__(self, bot):
        self.bot = bot

    @command(name='apply', help="Starts the application process")
    @is_not_applicant()
    async def apply(self, ctx):
        await ctx.author.create_dm()
        create_application(ctx.author)
        await send_question(ctx.author, 1, msg=parse(ctx.author, cfg.APPLIED))
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{ctx.author.mention} has started an application.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")

    @command(name='question', help="Used to switch to a given question. If no number is given, repeats the current question")
    @is_applicant()
    @commands.dm_only()
    async def question(self, ctx, Number=None):
        application = await get_application(ctx.author)
        if not await can_edit_questions(application):
            await ctx.author.dm_channel.send(parse(ctx.author, cfg.APP_CLOSED))
            return
        if Number is None:
            if application.status != "open":
                await ctx.author.dm_channel.send(parse(ctx.author, cfg.FINISHED))
                return
            await send_question(ctx.author, application.current_question)
            return
        num_questions = await get_num_questions(application)
        if not Number.isnumeric():
            raise NotNumberError(f"Argument must be a number between 1 and {num_questions}.")
        if not Number.isnumeric() or int(Number) < 1 or int(Number) > num_questions:
            raise NumberNotInRangeError(f"Number must be between 1 and {num_questions}.")
        await send_question(ctx.author, int(Number))
        application.current_question = int(Number)
        sessionSupp.commit()

    @command(name='overview', help="Display all questions that have already been answered")
    @is_applicant()
    async def overview(self, ctx):
        await send_overview(ctx.author, ctx=ctx)

    @command(name='submit', help="Submit your application and send it to the admins")
    @is_applicant()
    async def submit(self, ctx):
        application = await get_application(ctx.author)
        if await get_next_unanswered(application) > 0:
            await ctx.author.dm_channel.send("Please answer all questions first.")
            return
        if not await can_edit_questions(application):
            await ctx.author.dm_channel.send(parse(ctx.author, cfg.APP_CLOSED))
            return
        application.status = 'submitted'
        sessionSupp.commit()
        await ctx.author.dm_channel.send(parse(ctx.author, cfg.COMMITED))
        submission_date = datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        msg = f"{ctx.author.mention} has filled out the application. ({submission_date})\nYou can now either:\n`{cfg.PREFIX}accept <applicant> <message>`, `{cfg.PREFIX}reject <applicant> <message>` or `{cfg.PREFIX}review <applicant> <message>` (asking the Applicant to review their answers) it.\nIf <message> is omitted a default message will be sent.\nIf <applicant> is also omitted, it will try to target the last application."
        await send_overview(ctx.author, msg=msg, channel=cfg.CHANNEL[cfg.APPLICATIONS])

    @command(name='cancel', help="Cancel your application")
    @is_applicant()
    async def cancel(self, ctx):
        # can't cancel an application that's already approved or rejected
        application = await get_application(applicant=ctx.author)
        if application.status in ['rejected', 'approved']:
            return
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{ctx.author.mention} has canceled their application.")
        await ctx.author.dm_channel.send("Your application has been canceled.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")
        await delete_application(applicant=ctx.author)

    @command(name='accept', help="Accept the application. If message is ommitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def accept(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        # if no Applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await find_last_applicant(ctx, self.bot.user)
            if applicant is None:
                await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}accept <applicant>`.")
                return
        # confirm that there is a closed application for that Applicant
        applicant, address = await convert_user(ctx, applicant)
        application = await get_application(applicant)
        if not application:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {address}. Please verify that the name is written correctly and try again.")
            return
        elif await can_edit_questions(application):
            await cfg.CHANNEL[cfg.APPLICATIONS].send("Can't accept application while it's still being worked on.")
            return
        # remove Not Applied role
        if message:
            message = " ".join(message)
        if cfg.ROLE[cfg.NOT_APPLIED_ROLE] in applicant.roles:
            new_roles = applicant.roles
            new_roles.remove(cfg.ROLE[cfg.NOT_APPLIED_ROLE])
            await applicant.edit(roles=new_roles)

        # Whitelist Applicant
        SteamID64 = await find_steamID64(application)
        if SteamID64:
            result = await whitelist_player(ctx, SteamID64, applicant)
        else:
            result = "NoSteamIDinAnswer"

        # Send feedback about accepting the application
        if not message:
            message = parse(ctx.author, cfg.ACCEPTED)
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{address}'s application has been accepted.")
        await applicant.send("Your application was accepted:\n" + message)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been accepted.")

        # Send feedback about whitelisting success
        info = parse(ctx.author, "They have been informed to request whitelisting in {SUPPORT-REQUESTS}.")
        if result == "NoSteamIDinAnswer":
            await applicant.send("Whitelisting failed, you have given no valid SteamID64 your answer. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {address} failed. No valid SteamID64 found in answer:\n> {questions[application.steamID_row - 1].answer}\n{info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
        elif result == "IsGabesIDError" :
            await applicant.send("Whitelisting failed, you have given the example SteamID64 of Gabe Newell instead of your own. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {address} failed. Applicant gave Gabe Newells SteamID64. {info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. IsGabesIDError")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. IsGabesIDError")
        elif result.find("FailedError") >= 0:
            result = result[12:]
            await applicant.send("Whitelisting failed. " + parse(ctx.author, cfg.WHITELISTING_FAILED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Whitelisting {applicant.metion} failed (error message: {result}). {info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
        else:
            await applicant.send(parse(ctx.author, cfg.WHITELISTING_SUCCEEDED))
            await cfg.CHANNEL[cfg.APPLICATIONS].send(result)
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")

        # remove application from list of open applications
        application.status = 'approved'
        sessionSupp.commit()
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been accepted.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been accepted.")

    @command(name='reject', help="Reject the application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def reject(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        # if no Applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await find_last_applicant(ctx, self.bot.user)
            if applicant is None:
                cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}reject <applicant> <message>`.")
                return
        applicant, address = await convert_user(ctx, applicant)
        # confirm that there is a closed application for that Applicant
        application = await get_application(applicant)
        if not application:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {address}. Please verify that the name is written correctly and try again.")
            return
        elif await can_edit_questions(application):
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Can't reject application while it's still being worked on. Try {cfg.PREFIX}cancelapp <applicant> <message> instead.")
            return
        # Send feedback to applications channel and to Applicant
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{address}'s application has been rejected.")
        if not message:
            await applicant.send(parse(ctx.author, "Your application was rejected:\n" + cfg.REJECTED))
        else:
            await applicant.send("Your application was rejected:\n" + " ".join(message))
        # remove application from list of open applications
        application.status = "rejected"
        sessionSupp.commit()
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been rejected.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been rejected.")

    @command(name='review', help="Ask the Applicant to review their application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(cfg.ADMIN_ROLE)
    async def review(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        # if no Applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await find_last_applicant(ctx, self.bot.user)
            if applicant is None:
                await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{cfg.PREFIX}review <applicant> <message>`.")
                return
        applicant, address = await convert_user(ctx, applicant)
        # confirm that there is a closed application for that Applicant
        application = await get_application(applicant)
        if not application:
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Couldn't find a submitted application for {address}. Please verify that the name is written correctly and try again.")
            return
        elif await can_edit_questions(application):
            await cfg.CHANNEL[cfg.APPLICATIONS].send(f"Can't return application for review while it's still being worked on.")
            return
        # Send feedback to applications channel and to Applicant
        await cfg.CHANNEL[cfg.APPLICATIONS].send(f"{address}'s application has been returned.")
        explanation = f"\nYou can change the answer to any question by going to that question with `{cfg.PREFIX}question <number>` and then writing your new answer.\nYou can always review your current answers by entering `{cfg.PREFIX}overview`."
        if not message:
            await send_overview(applicant, "Your application was returned to you for review:\n" + cfg.REVIEWED + explanation)
        else:
            await send_overview(applicant, "Your application was returned to you for review:\n" + " ".join(message) + explanation)
        # remove application from list of open applications
        application.status = "review"
        sessionSupp.commit()
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been returned for review.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been returned for review.")

    @command(name='showapp', help="Displays the given Applicants application if it has been submitted. When Applicant is omitted, shows all applications.")
    @has_role(cfg.ADMIN_ROLE)
    async def showapp(self, ctx, *, Applicant=None):
        applicant = Applicant
        if applicant:
            applicant, address = await convert_user(ctx, applicant)
            application = await get_application(applicant)
            if not application:
                await ctx.channel.send(f"No application for {applicant} found")
            elif await can_edit_questions(application):
                await ctx.channel.send("Can't access application while it's still being worked on.")
            else:
                submission_date = datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC")
                msg = f"Overview of {ctx.author.mention}'s application. ({submission_date})"
                await send_overview(applicant, msg=msg, channel=ctx.channel)
            return
        else:
            applications = sessionSupp.query(Apps).filter(Apps.status.in_(['open', 'submitted', 'review', 'finished']))
            msg = "" if applications.count() > 0 else "No open applications right now."
            for application in applications:
                applicant, address = await convert_user(ctx, application.applicant)
                open_date = application.open_date.strftime("%d-%b-%Y %H:%M UTC")
                if await can_edit_questions(application):
                    msg += f"Applicant {address} is still working on their application. ({open_date})\n"
                else:
                    msg += f"Applicant {address} is **waiting for admin approval**. ({open_date})\n"
            if applications.count() > 0:
                msg += f"You can view a specific application by entering `{cfg.PREFIX}showapp <applicant>`."
            await ctx.channel.send(msg)
            return

    @command(name='cancelapp', help="Cancels the given application.")
    @has_role(cfg.ADMIN_ROLE)
    async def cancelapp(self, ctx, Applicant, *Message):
        applicant = Applicant
        message = Message
        applicant, address = await convert_user(ctx, applicant)
        application = await get_application(applicant)
        if not application:
            await ctx.channel.send(f"Applicant {address} couldn't be found.")
            return
        await delete_application(application)
        if message:
            message = " ".join(message)
        await ctx.channel.send(f"Application for {address} has been cancelled.")
        await applicant.send(f"Your application was cancelled by an administrator.{' Message: ' + message + '.' if len(message) > 0 else ''}")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been cancelled.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {applicant}'s application has been cancelled.")

    @command(name='reloadsheets', help="Updates all default messages and questions from google sheets.")
    @has_role(cfg.ADMIN_ROLE)
    async def reloadsheets(self, ctx):
        update_questions()
        await ctx.channel.send("Default messages and questions have been reloaded from google sheets.")
        logger.info("Default messages and questions have been reloaded from google sheets.")

def setup(bot):
    bot.add_cog(Applications(bot))
