import re
import config as saved
from discord.ext import commands
from discord.ext.commands import command
from valve import rcon
from datetime import datetime
from logger import logger
from config import *
from exiles_api import session, TextBlocks, Applications as AppsTable
from exceptions import *
from checks import *
from helpers import *

class Applications(commands.Cog, name="Application commands"):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def parse(user, msg):
        msg = str(msg).replace('{PREFIX}', PREFIX) \
                      .replace('{OWNER}', saved.GUILD.owner.mention)
        msg = msg.replace('{PLAYER}', user.mention) if type(user) == Member else msg.replace('{PLAYER}', str(user))
        for name, channel in saved.CHANNEL.items():
            msg = re.sub("(?i){" + name + "}", channel.mention, msg)
        for name, role in saved.ROLE.items():
            msg = re.sub("(?i){" + name + "}", role.mention, msg)
        return msg

    @staticmethod
    def get_question_msg(questions, author, id=1, msg=''):
        txt = questions[id-1].question
        num = len(questions)
        return f"{msg}\n__**Question {id} of {num}:**__\n> {Applications.parse(author, txt)}"

    @staticmethod
    def get_overview_msgs(questions, author, msg=''):
        give_overview = False
        for q in questions:
            if q.answer != '':
                give_overview = True
                break
        if not give_overview:
            return ["No questions answered yet!" + msg]
        buffer = ''
        num_questions = len(questions)
        overview = []
        for id in range(num_questions):
            if questions[id].answer != '':
                if len(buffer) + 21 + len(Applications.parse(author, questions[id].question)) > 2000:
                    overview.append(buffer)
                    buffer = ''
                buffer += f"__**Question {id + 1}:**__\n> {Applications.parse(author, questions[id].question)}\n"
                if len(buffer) + len(questions[id].answer) > 2000:
                    overview.append(buffer)
                    buffer = ''
                buffer += questions[id].answer + "\n"
        if msg and len(buffer) + len(msg) > 2000:
            overview.append(buffer)
            overview.append(msg)
        elif msg:
            overview.append(buffer + msg)
        else:
            overview.append(buffer)
        return overview

    @staticmethod
    def get_funcom_id_in_answer(questions, num):
        if questions:
            questions[num].answer
            # get all strings consisting only of the letters a-f and digits that's at least 10 characters long
            result = re.search(r'([a-fA-F0-9]{12,})', questions[num].answer)
            return result.group(1) if result else None

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
    def whitelist_player(funcom_id):
        try:
            msg = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, f"WhitelistPlayer {funcom_id}")
        except:
            with open(WHITELIST_PATH, 'r') as f:
                lines = f.readlines()
            # removed duplicates and lines with INVALID. Ensure that each line ends with a newline character
            filtered = set()
            for line in lines:
                if line != "\n" and not "INVALID" in line:
                    filtered.add(line.strip() + "\n")
            filtered.add(funcom_id + "\n")
            with open(WHITELIST_PATH, 'w') as f:
                f.writelines(['INVALID\n'] + list(filtered))
            msg = f"Player {funcom_id} added to whitelist."
        return msg

    @staticmethod
    async def get_last_applicant(ctx, user):
        async for message in ctx.channel.history(limit=100):
            if message.author == user:
                pos_end = message.content.find(" has filled out the application.")
                if pos_end < 0:
                    pos_end = message.content.find("'s application overview.")
                    if pos_end < 0:
                        continue
                pos_start = message.content.rfind("\n", 0, pos_end) + 1
                return message.content[pos_start:pos_end]
        return None

    @command(name='apply', help="Starts the application process")
    @is_not_applicant()
    async def apply(self, ctx):
        if ctx.author.dm_channel is None:
            await ctx.author.create_dm()
        new_app = AppsTable(ctx.author.id)
        session.add(new_app)
        session.commit()
        msg = self.parse(ctx.author, TextBlocks.get('APPLIED'))
        question = self.get_question_msg(new_app.questions, ctx.author, 1, msg)
        await ctx.author.dm_channel.send(question)
        await saved.CHANNEL[APPLICATIONS].send(f"{ctx.author} has started an application.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has started an application.")

    @command(name='question', help="Used to switch to a given question. If no number is given, repeats the current question")
    @is_applicant()
    @commands.dm_only()
    async def question(self, ctx, Number=None):
        if ctx.author.dm_channel is None:
            await ctx.author.create_dm()
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        if not app.can_edit_questions():
            await ctx.author.dm_channel.send(self.parse(ctx.author, TextBlocks.get('APP_CLOSED')))
            return
        if Number is None:
            if app.status != "open":
                await ctx.author.dm_channel.send(self.parse(ctx.author, TextBlocks.get('FINISHED')))
                return
            question = self.get_question_msg(app.questions, ctx.author, app.current_question)
            await ctx.author.dm_channel.send(question)
            return
        num_questions = len(app.questions)
        if not Number.isnumeric():
            raise NotNumberError(f"Argument must be a number between 1 and {num_questions}.")
        if not Number.isnumeric() or int(Number) < 1 or int(Number) > num_questions:
            raise NumberNotInRangeError(f"Number must be between 1 and {num_questions}.")
        question = self.get_question_msg(app.questions, ctx.author, int(Number))
        await ctx.author.dm_channel.send(question)
        app.current_question = int(Number)
        session.commit()

    @command(name='overview', help="Display all questions that have already been answered")
    @is_applicant()
    async def overview(self, ctx):
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        overview = self.get_overview_msgs(app.questions, ctx.author)
        for part in overview:
            await ctx.send(part)

    @command(name='submit', help="Submit your application and send it to the admins")
    @is_applicant()
    async def submit(self, ctx):
        if ctx.author.dm_channel is None:
            await ctx.author.create_dm()
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        if app.first_unanswered > 0:
            await ctx.author.dm_channel.send("Please answer all questions first.")
            return
        if not app.can_edit_questions():
            await ctx.author.dm_channel.send(self.parse(ctx.author, TextBlocks.get('APP_CLOSED')))
            return
        app.status = 'submitted'
        app.open_date = datetime.utcnow()
        session.commit()
        await ctx.author.dm_channel.send(self.parse(ctx.author, TextBlocks.get('COMMITED')))
        submission_date = datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has submitted their application.")
        msg = f"{ctx.author.mention} has filled out the application. ({submission_date})\nYou can now either:\n`{PREFIX}accept <applicant> <message>`, `{PREFIX}reject <applicant> <message>` or `{PREFIX}review <applicant> <message>` (asking the Applicant to review their answers) it.\nIf <message> is omitted a default message will be sent.\nIf <applicant> is also omitted, it will try to target the last application."
        overview = self.get_overview_msgs(app.questions, ctx.author, msg)
        for part in overview:
            await saved.CHANNEL[APPLICATIONS].send(part)

    @command(name='cancel', help="Cancel your application")
    @is_applicant()
    async def cancel(self, ctx):
        app = session.query(AppsTable).filter_by(disc_id=ctx.author.id).one()
        # can't cancel an application that's already approved or rejected
        if app.status in ('rejected', 'approved'):
            return
        session.delete(app)
        session.commit()
        await saved.CHANNEL[APPLICATIONS].send(f"{ctx.author} has canceled their application.")
        await ctx.author.dm_channel.send("Your application has been canceled.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {ctx.author} has canceled their application.")

    @command(name='accept', help="Accept the application. If message is ommitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(ADMIN_ROLE)
    async def accept(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        # if no Applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await self.get_last_applicant(ctx, self.bot.user)
            if applicant is None:
                await saved.CHANNEL[APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{PREFIX}accept <applicant>`.")
                return
        member = await self.get_member(ctx, applicant)
        if not member:
            await saved.CHANNEL[APPLICATIONS].send(f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? Users who leave the server while they still have an open application are automatically removed. Use {PREFIX}showapp to check if the app is still there.")
        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            await ctx.send(f"Couldn't find a submitted application for {member}. Please verify that the name is written correctly and try again.")
            return
        elif app.can_edit_questions():
            await ctx.send("Can't accept application while it's still being worked on.")
            return
        # remove Not Applied role
        if saved.ROLE[NOT_APPLIED_ROLE] in member.roles:
            new_roles = member.roles
            new_roles.remove(ROLE[NOT_APPLIED_ROLE])
            await member.edit(roles=new_roles)

        # Whitelist Applicant
        funcom_id = self.get_funcom_id_in_answer(app.questions, app.funcom_id_row-1)
        if funcom_id:
            result = self.whitelist_player(funcom_id)
            user = session.query(Users).filter_by(disc_id=member.id).first()
            if user:
                user.disc_user = str(member)
                user.funcom_id = funcom_id
            else:
                new_user = Users(disc_user=str(member), disc_id=member.id, funcom_id=funcom_id)
                session.add(new_user)
        else:
            result = "NoFuncomIDinAnswer"

        # remove application from list of open applications
        app.status = 'approved'
        session.commit()
        if message:
            message = " ".join(message)
        else:
            message = self.parse(ctx.author, TextBlocks.get('ACCEPTED'))
        await ctx.send(f"{member}'s application has been accepted.")
        await member.send("Your application was accepted:\n" + message)
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been accepted.")

        # Send feedback about whitelisting success
        info = self.parse(ctx.author, "They have been informed to request whitelisting in {SUPPORT-REQUEST}.")
        if result == "NoFuncomIDinAnswer":
            await member.send("Whitelisting failed, you have given no valid FuncomId your answer. " + self.parse(member, TextBlocks.get('WHITELISTING_FAILED')))
            await saved.CHANNEL[APPLICATIONS].send(f"Whitelisting {member} failed. No valid FuncomID found in answer:\n> {questions[app.funcom_id_row - 1].answer}\n{info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. NoSteamIDinAnswer")
        elif result.find("FailedError") >= 0:
            result = result[12:]
            await member.send("Whitelisting failed. " + self.parse(member, TextBlocks.get('WHITELISTING_FAILED')))
            await saved.CHANNEL[APPLICATIONS].send(f"Whitelisting {member} failed (error message: {result}). {info}")
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. FailedError (error: {result})")
        else:
            await member.send(self.parse(ctx.author, TextBlocks.get('WHITELISTING_SUCCEEDED')))
            await saved.CHANNEL[APPLICATIONS].send(result)
            print(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")
            logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {result}")

        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been accepted.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been accepted.")

    @command(name='reject', help="Reject the application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(ADMIN_ROLE)
    async def reject(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        # if no Applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await self.get_last_applicant(ctx, self.bot.user)
            if applicant is None:
                await saved.CHANNEL[APPLICATIONS].send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{PREFIX}reject <applicant> <message>`.")
                return
        member = await self.get_member(ctx, applicant)
        if not member:
            await saved.CHANNEL[APPLICATIONS].send(f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? Users who leave the server while they still have an open application are automatically removed. Use {PREFIX}showapp to check if the app is still there.")
        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            await ctx.send(f"Couldn't find a submitted application for {member}. Please verify that the name is written correctly and try again.")
            return
        elif app.can_edit_questions():
            await ctx.send(f"Can't reject application while it's still being worked on. Try {PREFIX}cancelapp <applicant> <message> instead.")
            return

        # remove application from list of open applications
        app.status = "rejected"
        session.commit()

        await ctx.send(f"{member}'s application has been rejected.")
        if not message:
            await member.send(self.parse(ctx.author, "Your application was rejected:\n" + TextBlocks.get('REJECTED')))
        else:
            await member.send("Your application was rejected:\n> " + " ".join(message))
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been rejected.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been rejected.")

    @command(name='review', help="Ask the Applicant to review their application. If message is omitted a default message will be sent. If message and Applicant are omitted target the last submitted application.")
    @has_role(ADMIN_ROLE)
    async def review(self, ctx, Applicant=None, *Message):
        applicant = Applicant
        message = Message
        # if no Applicant is given, try to automatically determine one
        if applicant is None:
            applicant = await self.get_last_applicant(ctx, self.bot.user)
            if applicant is None:
                await ctx.send(f"Couldn't find a submitted application within the last 100 messages. Please specify the Applicant via `{PREFIX}review <applicant> <message>`.")
                return
        member = await self.get_member(ctx, applicant)
        if not member:
            await saved.CHANNEL[APPLICATIONS].send(f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? Users who leave the server while they still have an open application are automatically removed. Use {PREFIX}showapp to check if the app is still there.")
        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            await ctx.send(f"Couldn't find a submitted application for {member}. Please verify that the name is written correctly and try again.")
            return
        elif app.can_edit_questions():
            await ctx.send(f"Can't return application for review while it's still being worked on.")
            return

        # remove application from list of open applications
        app.status = "review"
        session.commit()

        await ctx.send(f"{member}'s application has been returned.")
        explanation = f"\nYou can change the answer to any question by going to that question with `{PREFIX}question <number>` and then writing your new answer.\nYou can always review your current answers by entering `{PREFIX}overview`."
        if not message:
            msg = "Your application was returned to you for review:\n" + TextBlocks.get('REVIEWED') + explanation
        else:
            msg = "Your application was returned to you for review:\n> " + " ".join(message) + explanation
        overview = self.get_overview_msgs(app.questions, member, msg)
        for part in overview:
            if member.dm_channel is None:
                await member.create_dm()
            await member.dm_channel.send(part)
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been returned for review.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been returned for review.")

    @command(name='showapp', help="Displays the given Applicants application if it has been submitted. When Applicant is omitted, shows all applications.")
    @has_role(ADMIN_ROLE)
    async def showapp(self, ctx, *, Applicant=None):
        applicant = Applicant
        if applicant:
            member = await self.get_member(ctx, applicant)
            if not member:
                await ctx.send(f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? Users who leave the server while they still have an open application are automatically removed. Use {PREFIX}showapp without a name to get a list of all active applications.")
            app = session.query(AppsTable).filter_by(disc_id=member.id).first()
            if not app:
                await ctx.send(f"No application for {member} found")
            elif app.can_edit_questions():
                await ctx.send("Can't access application while it's still being worked on.")
            else:
                submission_date = app.open_date.strftime("%d-%b-%Y %H:%M UTC")
                msg = f"{member}'s application overview. ({submission_date})"
                overview = self.get_overview_msgs(app.questions, member, msg)
                for part in overview:
                    await ctx.send(part)
            return
        else:
            display = ['open', 'submitted', 'review', 'finished']
            apps = session.query(AppsTable).filter(AppsTable.status.in_(display)).all()
            msg = "" if len(apps) > 0 else "No open applications right now."
            for app in apps:
                member = await self.get_member(ctx, app.disc_id)
                open_date = app.open_date.strftime("%d-%b-%Y %H:%M UTC")
                if app.can_edit_questions():
                    msg += f"Applicant **{member}** is **still working** on their application. (Application started on {open_date})\n"
                else:
                    msg += f"Applicant **{member}** is **waiting for admin approval**. (Application submitted on {open_date})\n"
            if len(apps) > 0:
                msg += f"You can view a specific application by entering `{PREFIX}showapp <applicant>`."
            await ctx.channel.send(msg)
            return

    @command(name='cancelapp', help="Cancels the given application.")
    @has_role(ADMIN_ROLE)
    async def cancelapp(self, ctx, Applicant, *Message):
        applicant = Applicant
        message = Message
        member = await self.get_member(ctx, applicant)
        if not member:
            await saved.CHANNEL[APPLICATIONS].send(f"Couldn't get id for {applicant}. Are you sure they are still on this discord server? Users who leave the server while they still have an open application are automatically removed. Use {PREFIX}showapp to check if the app is still there.")
        # confirm that there is a closed application for that Applicant
        app = session.query(AppsTable).filter_by(disc_id=member.id).first()
        if not app:
            await ctx.send(f"Couldn't find an application for {member}. Please verify that the name is written correctly and try again.")
            return
        if app.status in ('approved', 'rejected'):
            await ctx.send(f"Can't cancel an application that was already accepted or rejected.")
            return
        session.delete(app)
        session.commit()
        await ctx.send(f"Application for {member} has been cancelled.")
        if message:
            await member.send(f"Your application was cancelled by an administrator.\n> {' '.join(message)}")
        else:
            await member.send(f"Your application was cancelled by an administrator.")
        print(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been cancelled.")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}. {member}'s application has been cancelled.")

def setup(bot):
    bot.add_cog(Applications(bot))
