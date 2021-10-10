import re
from discord.ext import commands
from discord.ext.commands import command
from datetime import datetime
from logger import logger
from checks import is_not_applicant, is_applicant, has_role
from config import APPLICATIONS, PREFIX, ADMIN_ROLE, NOT_APPLIED_ROLE, SUPPORT
from exiles_api import session, TextBlocks, Users, Applications as AppsTable
from exceptions import NotNumberError, NumberNotInRangeError
from functions import parse, get_guild, get_channels, get_member, get_roles, whitelist_player


class Applications(commands.Cog, name="Application commands"):
    def __init__(self, bot):
        self.bot = bot
        self.guild = get_guild(bot)

    @staticmethod
    async def get_question_msg(guild, questions, author, id=1, msg=""):
        txt = questions[id - 1].question
        num = len(questions)
        return f"{msg}\n__**Question {id} of {num}:**__\n> {parse(guild, author, txt)}"

    @staticmethod
    async def get_overview_msgs(questions, author, guild, msg=""):
        give_overview = False
        for q in questions:
            if q.answer != "":
                give_overview = True
                break
        if not give_overview:
            return ["No questions answered yet!" + msg]
        chunk = ""
        overview = []
        for id in range(len(questions)):
            answer = questions[id].answer + "\n"
            question = f"__**Question {id + 1}:**__\n> {parse(guild, author, questions[id].question)}\n"
            if answer != "":
                if len(chunk) + len(question) >= 2000:
                    overview.append(chunk)
                    chunk = ""
                chunk += question
                if len(chunk) + len(answer) >= 2000:
                    overview.append(chunk)
                    chunk = ""
                chunk += answer
        if msg and len(chunk) + len(msg) >= 2000:
            overview.append(chunk)
            overview.append(msg)
        elif msg:
            overview.append(chunk + msg)
        else:
            overview.append(chunk)
        return overview

    @staticmethod
    async def get_funcom_id_in_text(text, upper_case=True):
        # get all strings consisting only of the letters a-f and digits that's at
        # least 14 and at most 16 characters long
        result = re.search(r"([a-fA-F0-9]{14,16})", text)
        if not result:
            return None
        funcom_id = result.group(1)
        start = text.find(funcom_id)
        end = start + len(funcom_id) - 1
        # if given funcom_id isn't either at the beginning and/or end of the text or delimited by a blank
        if (start > 0 and text[start - 1] != " ") or (end < len(text) - 1 and text[end + 1] != " "):
            return None
        if funcom_id and upper_case:
            return funcom_id.upper()
        elif funcom_id and not upper_case:
            return funcom_id
        else:
            return None

    @staticmethod
    async def get_last_applicant(ctx, bot, applicant):
        channels = get_channels(bot=bot)
        async for message in channels[APPLICATIONS].history(limit=100):
            if message.author == bot.user:
                pos_end = message.content.find(" has filled out the application.")
                if pos_end < 0:
                    pos_end = message.content.find("'s application overview.")
                    if pos_end < 0:
                        continue
                pos_start = message.content.rfind("\n", 0, pos_end) + 1
                applicant = message.content[pos_start:pos_end]
                if applicant:
                    return await get_member(ctx, applicant)
        return None

    @staticmethod
    async def add_new_user(member, funcom_id):
        user = session.query(Users).filter_by(disc_id=member.id).first()
        if user:
            user.disc_user = str(member)
            user.funcom_id = funcom_id
        else:
            new_user = Users(disc_user=str(member), disc_id=member.id, funcom_id=funcom_id)
            session.add(new_user)
        session.commit()

    @command(name="apply", help="Starts the application process")
    @is_not_applicant()
    async def apply(self, ctx):
        guild = get_guild(self.bot)
        channels = get_channels(guild)
        if ctx.author.dm_channel is None:
            await ctx.author.create_dm()
        new_app = AppsTable(ctx.author.id)
        session.add(new_app)
        session.commit()
        msg = parse(guild, ctx.author, TextBlocks.get("APPLIED"))
        question = await self.get_question_msg(guild, new_app.questions, ctx.author, 1, msg)
        await ctx.author.dm_channel.send(question)
        await channels[APPLICATIONS].send(f"{ctx.author} has started an application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")

    @command(
        name="question",
        help="Used to switch to a given question. " "If no number is given, repeats the current question",
    )
    @is_applicant()
    @commands.dm_only()
    async def question(self, ctx, Number=None):
        guild = get_guild(self.bot)
        if ctx.author.dm_channel is None:
            await ctx.author.create_dm()
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        if not app.can_edit_questions():
            await ctx.author.dm_channel.send(parse(guild, ctx.author, TextBlocks.get("APP_CLOSED")))
            return
        if Number is None:
            if app.status != "open":
                await ctx.author.dm_channel.send(parse(guild, ctx.author, TextBlocks.get("FINISHED")))
                return
            question = await self.get_question_msg(guild, app.questions, ctx.author, app.current_question)
            await ctx.author.dm_channel.send(question)
            return
        num_questions = len(app.questions)
        if not Number.isnumeric():
            raise NotNumberError(f"Argument must be a number between 1 and {num_questions}.")
        if not Number.isnumeric() or int(Number) < 1 or int(Number) > num_questions:
            raise NumberNotInRangeError(f"Number must be between 1 and {num_questions}.")
        question = await self.get_question_msg(guild, app.questions, ctx.author, int(Number))
        await ctx.author.dm_channel.send(question)
        app.current_question = int(Number)
        session.commit()

    @command(name="overview", help="Display all questions that have already been answered")
    @is_applicant()
    async def overview(self, ctx):
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        overview = await self.get_overview_msgs(app.questions, ctx.author, self.guild)
        for part in overview:
            await ctx.send(part)

    @command(name="submit", help="Submit your application and send it to the admins")
    @is_applicant()
    async def submit(self, ctx):
        guild = get_guild(self.bot)
        roles = get_roles(guild)
        channels = get_channels(guild)
        if ctx.author.dm_channel is None:
            await ctx.author.create_dm()
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        if app.first_unanswered > 0:
            await ctx.author.dm_channel.send("Please answer all questions first.")
            return
        if not app.can_edit_questions():
            await ctx.author.dm_channel.send(parse(guild, ctx.author, TextBlocks.get("APP_CLOSED")))
            return
        app.status = "submitted"
        app.open_date = datetime.utcnow()
        session.commit()
        await ctx.author.dm_channel.send(parse(guild, ctx.author, TextBlocks.get("COMMITED")))
        submission_date = datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC")
        logger.info(
            f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application."
        )
        msg = (
            f"{roles[ADMIN_ROLE].mention}\n"
            f"{ctx.author.mention} has filled out the application. ({submission_date})\n"
            f"You can now either:\n"
            f"`{PREFIX}accept <applicant> <message>`, `{PREFIX}reject <applicant> <message>` or "
            f"`{PREFIX}review <applicant> <message>` (asking the Applicant to review their answers) it.\n"
            f"If <message> is omitted a default message will be sent.\n"
            f"If <applicant> is also omitted, it will try to target the last application. "
        )
        overview = await self.get_overview_msgs(app.questions, ctx.author, self.guild, msg)
        for part in overview:
            await channels[APPLICATIONS].send(part)

    @command(name="cancel", help="Cancel your application")
    @is_applicant()
    async def cancel(self, ctx):
        anc = f"Author: {ctx.author} / Command: {ctx.message.content}."
        channels = get_channels(bot=self.bot)
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        # can't cancel an application that's already approved or rejected
        if app.status in ("rejected", "approved"):
            await ctx.send(" Can't cancel an application that's already approved or rejected.")
            logger.info(f"{anc} Can't cancel an application that's already approved or rejected.")
            return

        session.delete(app)
        session.commit()
        await channels[APPLICATIONS].send(f"{ctx.author} has canceled their application.")
        await ctx.author.dm_channel.send("Your application has been canceled.")
        logger.info(f"{anc} {ctx.author} has canceled their application.")

    @command(
        name="accept",
        help="Accept the application. If message is ommitted a default message will be sent. "
        "If message and Applicant are omitted target the last submitted application.",
    )
    @has_role(ADMIN_ROLE)
    async def accept(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        guild = get_guild(self.bot)
        roles = get_roles(guild)
        channels = get_channels(guild)

        # convert applicant string to member.
        if applicant:
            member = await get_member(ctx, applicant)
            if not member:
                msg = (
                    f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? "
                    "Users who leave the server while they still have an open application are "
                    f"automatically removed. Use {PREFIX}showapp to check if the app is still there."
                )
                await channels[APPLICATIONS].send(msg)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
                return

        # If no applicant was given, try to determine them from the channel history
        else:
            member = await self.get_last_applicant(ctx, self.bot, applicant)
            if not member:
                msg = (
                    "Couldn't find a submitted application within the last 100 messages. "
                    f"Please specify the Applicant via `{PREFIX}accept <applicant> <message>`."
                )
                await channels[APPLICATIONS].send(msg)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
                return

        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            msg = (
                f"Couldn't find a submitted application for {member}. "
                "Please verify that the name is written correctly and try again."
            )
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        elif app.can_edit_questions():
            msg = "Can't accept application while it's still being worked on."
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return

        # remove Not Applied role
        if roles[NOT_APPLIED_ROLE] in member.roles:
            await member.remove_roles(roles[NOT_APPLIED_ROLE])

        # remove application from list of open applications
        app.status = "approved"
        session.commit()

        if message:
            await member.send("Your application was accepted:\n" + " ".join(message))
        else:
            message = parse(guild, ctx.author, TextBlocks.get("ACCEPTED"))
            await member.send("Your application was accepted:\n" + message)

        await ctx.send(f"{member}'s application has been accepted.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been accepted.")

        # Whitelist Applicant
        text = app.questions[app.funcom_id_row - 1].answer
        funcom_id = await self.get_funcom_id_in_text(text)
        info = parse(guild, ctx.author, f"They have been informed to request whitelisting in {channels[SUPPORT]}.")
        if funcom_id:
            funcom_id = funcom_id.upper()
            result, err = whitelist_player(funcom_id)
            if result == f"Player {funcom_id} added to whitelist.":
                await self.add_new_user(member, funcom_id)
                await member.send(parse(guild, ctx.author, TextBlocks.get("WHITELISTING_SUCCEEDED")))
                await channels[APPLICATIONS].send(result)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            elif result.find("FailedError") >= 0:
                result = result[12:]
                await channels[APPLICATIONS].send(f"Whitelisting {member} failed (error message: {result}). {info}")
                await member.send(
                    "Whitelisting failed. " + (parse(guild, member, TextBlocks.get("WHITELISTING_FAILED")))
                )
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
            else:
                await member.send(
                    "Whitelisting failed. " + (parse(guild, member, TextBlocks.get("WHITELISTING_FAILED")))
                )
                await channels[APPLICATIONS].send(f"Whitelisting {member} failed (error message: {result}). {info}")
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")

        else:
            await member.send(
                "Whitelisting failed, you have given no valid FuncomId your answer. "
                + (parse(guild, member, TextBlocks.get("WHITELISTING_FAILED")))
            )
            await channels[APPLICATIONS].send(
                f"Whitelisting {member} failed. No valid FuncomID found in answer:\n"
                f"> {app.questions[app.funcom_id_row - 1].answer}\n{info}"
            )
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")

    @command(
        name="reject",
        help="Reject the application. If message is omitted a default message will be sent. "
        "If message and Applicant are omitted target the last submitted application.",
    )
    @has_role(ADMIN_ROLE)
    async def reject(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        guild = get_guild(self.bot)
        channels = get_channels(guild)

        # convert applicant string to member.
        if applicant:
            member = await get_member(ctx, applicant)
            if not member:
                msg = (
                    f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? "
                    "Users who leave the server while they still have an open application are "
                    f"automatically removed. Use {PREFIX}showapp to check if the app is still there."
                )
                await channels[APPLICATIONS].send(msg)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
                return

        # If no applicant was given, try to determine them from the channel history
        else:
            member = await self.get_last_applicant(ctx, self.bot, applicant)
            if not member:
                msg = (
                    "Couldn't find a submitted application within the last 100 messages. "
                    f"Please specify the Applicant via `{PREFIX}reject <applicant> <message>`."
                )
                await channels[APPLICATIONS].send(msg)
                logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
                return

        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            msg = (
                f"Couldn't find a submitted application for {member}. "
                "Please verify that the name is written correctly and try again."
            )
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return
        elif app.can_edit_questions():
            msg = (
                "Can't reject application while it's still being worked on. "
                f"Try {PREFIX}cancelapp <applicant> <message> instead."
            )
            await ctx.send(msg)
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {msg}")
            return

        # remove application from list of open applications
        app.status = "rejected"
        session.commit()

        if not message:
            await member.send(parse(guild, ctx.author, "Your application was rejected:\n" + TextBlocks.get("REJECTED")))
        else:
            await member.send("Your application was rejected:\n> " + " ".join(message))

        await ctx.send(f"{member}'s application has been rejected.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been rejected.")

    @command(
        name="review",
        help="Ask the applicant to review their application. "
        "If message is omitted a default message will be sent. "
        "If message and Applicant are omitted target the last submitted application.",
    )
    @has_role(ADMIN_ROLE)
    async def review(self, ctx, Applicant=None, *Message):
        anc = f"Author: {ctx.author} / Command: {ctx.message.content}."
        applicant = Applicant
        message = Message
        channels = get_channels(bot=self.bot)

        # convert applicant string to member.
        if applicant:
            member = await get_member(ctx, applicant)
            if not member:
                msg = (
                    f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? "
                    "Users who leave the server while they still have an open application are "
                    f"automatically removed. Use {PREFIX}showapp to check if the app is still there."
                )
                await channels[APPLICATIONS].send(msg)
                logger.info(f"{anc} {msg}")
                return

        # If no applicant was given, try to determine them from the channel history
        else:
            member = await self.get_last_applicant(ctx, self.bot, applicant)
            if not member:
                msg = (
                    "Couldn't find a submitted application within the last 100 messages. "
                    f"Please specify the Applicant via `{PREFIX}review <applicant> <message>`."
                )
                await channels[APPLICATIONS].send(msg)
                logger.info(f"{anc} {msg}")
                return

        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            msg = (
                f"Couldn't find a submitted application for {member}. "
                f"Please verify that the name is written correctly and try again."
            )
            await ctx.send(msg)
            logger.info(f"{anc} {msg}")
            return
        elif app.can_edit_questions():
            msg = "Can't return application for review while it's still being worked on."
            await ctx.send(msg)
            logger.info(f"{anc} {msg}")
            return

        # remove application from list of open applications
        app.status = "review"
        session.commit()

        explanation = (
            f"\nYou can change the answer to any question by going to that question with "
            f"`{PREFIX}question <number>` and then writing your new answer.\n"
            f"You can always review your current answers by entering `{PREFIX}overview`."
        )
        if not message:
            msg = "Your application was returned to you for review:\n" + TextBlocks.get("REVIEWED") + explanation
        else:
            msg = "Your application was returned to you for review:\n> " + " ".join(message) + explanation

        await ctx.send(f"{member}'s application has been returned.")
        overview = await self.get_overview_msgs(app.questions, member, self.guild, msg)
        for part in overview:
            if member.dm_channel is None:
                await member.create_dm()

            await member.dm_channel.send(part)
        logger.info(f"{anc} {member}'s application has been returned for review.")

    @command(
        name="showapp",
        aliases=["showapps"],
        help="Displays the given Applicants application if it has been submitted. "
        "If applicant is omitted, shows all applications.",
    )
    @has_role(ADMIN_ROLE)
    async def showapp(self, ctx, *, Applicant=None):
        anc = f"Author: {ctx.author} / Command: {ctx.message.content}."
        applicant = Applicant
        if applicant:
            member = await get_member(ctx, applicant)
            if not member:
                await ctx.send(
                    f"Couldn't get id for {applicant}. "
                    f"Are you sure they are still on this discord server? "
                    f"Users who leave the server while they still have an open application are automatically removed. "
                    f"Use {PREFIX}showapp without a name to get a list of all active applications."
                )

            app = session.query(AppsTable).filter_by(disc_id=member.id).first()
            if not app:
                await ctx.send(f"No application for {member} found.")
                logger.info(f"{anc} No application for {member} found.")
            elif app.can_edit_questions():
                await ctx.send("Can't access application while it's still being worked on.")
                logger.info(f"{anc} Can't access application while it's still being worked on.")
            else:
                submission_date = app.open_date.strftime("%d-%b-%Y %H:%M UTC")
                msg = f"{member}'s application overview. ({submission_date})"
                overview = await self.get_overview_msgs(app.questions, member, self.guild, msg)
                for part in overview:
                    await ctx.send(part)
                logger.info(f"{anc} Sending {member}'s application overview.")

            return

        else:
            display = ["open", "submitted", "review", "finished"]
            apps = session.query(AppsTable).filter(AppsTable.status.in_(display)).all()
            msg = "" if len(apps) > 0 else "No open applications right now."
            for app in apps:
                member = await get_member(ctx, app.disc_id)
                open_date = app.open_date.strftime("%d-%b-%Y %H:%M UTC")
                if app.can_edit_questions():
                    msg += (
                        f"Applicant **{member}** is **still working** on their application. "
                        f"(Application started on {open_date})\n"
                    )
                else:
                    msg += (
                        f"Applicant **{member}** is **waiting for admin approval**. "
                        f"(Application submitted on {open_date})\n"
                    )

            if len(apps) > 0:
                msg += f"You can view a specific application by entering `{PREFIX}showapp <applicant>`."

            await ctx.channel.send(msg)
            logger.info(f"{anc} {msg}")
            return

    @command(name="cancelapp", help="Cancels the given application.")
    @has_role(ADMIN_ROLE)
    async def cancelapp(self, ctx, Applicant, *Message):
        anc = f"Author: {ctx.author} / Command: {ctx.message.content}."
        applicant = Applicant
        message = Message
        member = await get_member(ctx, applicant)
        channels = get_channels(bot=self.bot)
        if not member:
            await channels[APPLICATIONS].send(
                f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? "
                f"Users who leave the server while they still have an open application are automatically removed. "
                f"Use {PREFIX}showapp to check if the app is still there."
            )
            logger.info(f"{anc} Couldn't get id for {applicant}.")
            return

        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            await ctx.send(
                f"Couldn't find an application for {member}. "
                f"Please verify that the name is written correctly and try again."
            )
            logger.info(f"{anc} Couldn't find an application for {member}.")
            return

        if app.status in ("approved", "rejected"):
            await ctx.send("Can't cancel an application that was already accepted or rejected.")
            logger.info(f"{anc} Can't cancel an application that was already accepted or rejected.")
            return

        session.delete(app)
        session.commit()
        await ctx.send(f"Application for {member} has been cancelled.")
        if message:
            await member.send(f"Your application was cancelled by an administrator.\n> {' '.join(message)}")
        else:
            await member.send("Your application was cancelled by an administrator.")

        logger.info(f"{anc}. {member}'s application has been cancelled.")


def setup(bot):
    bot.add_cog(Applications(bot))
