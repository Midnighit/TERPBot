import random
# from math import ceil
from discord import Member
from discord.ext import commands
from discord.ext.commands import command, group
from logger import logger
from config import *
from exiles_api import *
from functions import *

# rowboat birthday 25-July - potential reveal day?
class BBK(commands.Cog, name="Boatbucks commands."):
    def __init__(self, bot):
        self.bot = bot
        self.master_id = 440871726285324288
        self.permitted = [self.master_id, 221332467410403328, 136678918005456896]
        self.bbk = "<:boatbuck:817400070072696833>"

    @group(help="Commands to pay and get paid with boatbucks...if you're lucky.")
    async def boatbucks(self, ctx):
        if ctx.author.id in self.permitted:
            if ctx.invoked_subcommand is None:
                await ctx.send("I have no idea what you want from me. I can either "
                              f"`{PREFIX}boatbucks give <boatbucks> <user>` or "
                              f"`{PREFIX}boatbucks take <boatbucks> <user>` for you.")
        else:
            if ctx.invoked_subcommand is None:
                user = session.query(Boatbucks).get(ctx.author.id)
                if user is None or user.bucks == 0:
                    await ctx.send(f"You don't have any {self.bbk}. "
                                   f"Maybe you can earn some if you ask <@{self.master_id}> nicely!")
                else:
                    await ctx.send(f"You currently have {user.bucks} {self.bbk}. Don't spend them all in one place!")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @boatbucks.command(aliases=['pay'], help="Pay boatbucks to another player from your own account... or just print them if you own the boatbank.")
    async def give(self, ctx, bucks: int, member: Member):
        # sender tries to send a negative amount of bucks (i.e. gaining bucks)
        if bucks < 0:
            replies = [("Ok, I get it. It was fun while it lasted but no more giving of negative amounts anymore!")]
        # sender and recipient of the boatbucks are the same person
        elif ctx.author.id == member.id:
            replies = [("Trying to send boatbucks to yourself, huh? "
                        "You think you're very clever don't you? Sorry, but no dice!")]
        # both sender and recipient are able to create and take away boatbucks at will
        elif ctx.author.id in self.permitted and member.id in self.permitted:
            replies = [(f"Oh c'mon. You known that {member.mention} already has unlimited credit with the boatbank!")]
        # sender can create and take away boatbucks at will
        elif ctx.author.id in self.permitted:
            recipient = session.query(Boatbucks).get(member.id)
            if not recipient:
                recipient = Boatbucks(id=member.id, bucks=bucks)
                session.add(recipient)
            else:
                recipient.bucks += bucks
            session.commit()
            replies = [(f"Sure boss. Created **{bucks}** {self.bbk} out of thin air for {member.mention}. "
                        f"I hope you know what you're doing..."),
                       (f"Here I am, brain the size of a planet, and they tell me to give {member.mention} **{bucks}** "
                        f"{self.bbk}. Call that job satisfaction? 'Cos I don't."),
                       (f"Are you sure {member.mention} really deserves it? Fine, fine transferring **{bucks}** "
                        f"{self.bbk} to their account. _dramatic sigh_"),
                       (f"Firing up the money printing machine. **{bucks}** "
                        f"{self.bbk} for {member.mention} coming right up!")]
        else:
            sender = session.query(Boatbucks).get(ctx.author.id)
            if not sender or sender.bucks < bucks:
                # sender has no boatbucks at all
                if not sender or sender.bucks == 0:
                    replies = [(f"You don't have a single penny, much less a whole boatbuck right now. "
                                f"Try earning some boatbucks with <@{self.master_id}> first!")]
                # sender doesn't have as many bucks as they want to send
                else:
                    replies = [(f"Nice try but you only have **{sender.bucks}** {self.bbk}. "
                                f"Try to earn some with <@{self.master_id}> first!")]
            else:
                sender.bucks -= bucks
                # recipient can create and take away boatbucks at will
                if member.id in self.permitted:
                    replies = [(f"Destroying **{bucks}** {self.bbk} for you. "
                                f"{member.mention} doesn't need them anyway."),
                               (f"Sure, let's fight inflation and remove **{bucks}** {self.bbk} from circulation. "
                                f"{member.mention} has unlimited credit at the boatbank anyway.")]
                # default case sender and recipient are normal and sender has enough bucks
                else:
                    recipient = session.query(Boatbucks).get(member.id)
                    if not recipient:
                        recipient = Boatbucks(id=member.id, bucks=bucks)
                        session.add(recipient)
                    else:
                        recipient.bucks += bucks
                    replies = [(f"Alright, transferring **{bucks}** {self.bbk} from your account to {member.mention}. "
                                f"It's your money. ¯\_(ツ)_/¯"),
                               (f"Another **{bucks}** {self.bbk} further away from buying your own yacht. "
                                f"Maybe {member.mention} will be able to afford a rowboat after this transaction."),
                               (f"Feeling generous, huh? Very well your loss of **{bucks}** "
                                f"{self.bbk} will be {member.mention}'s gain.")]
                session.commit()
        await ctx.send(random.choice(replies))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @give.error
    async def give_error(self, ctx, error):
        pe(error)
        GlobalVars.set_value("caught", 1)
        if isinstance(error, commands.errors.MissingRequiredArgument):
            if error.param.name == "member":
                await ctx.send("You need to give me the name of the user you dummy!")
            elif error.param.name == "bucks":
                await ctx.send("Soooo just _how_ many boatbucks am I supposed to give?")
        elif isinstance(error, commands.errors.BadArgument):
            await ctx.send(f"Sorry but who tf is **{error.argument}** supposed to be?")
        else:
            pe(error)
            logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")

    @boatbucks.command(name="take", help="Withdraw a given amount of boatbucks from some poor soul. As befits such a tyrannical command, it's only available to Rowboat and her henchmen at the boatbank.")
    async def take(self, ctx, bucks: int, member: Member):
        # sender can't create and take away boatbucks at will
        if ctx.author.id not in self.permitted:
            replies = [(f"No can do. Only <@{self.master_id}> and her henchmen from the boatbank are allowed to "
                         "take other peoples boatbucks without asking for permission. "
                         "Sorry mate, the world just ain't fair.")]
        # recipient can create and take away boatbucks at will
        elif member.id in self.permitted:
            replies = [("Hey, you can't take away boatbucks from a fellow employee at the boatbank. "
                        "You may have to talk to Midnight if you want to have them fired for good.")]
        else:
            recipient = session.query(Boatbucks).get(member.id)
            # recipient has no boatbucks at all
            if not recipient or recipient.bucks == 0:
                replies = [("As much as I enjoy taking away money from hapless vict... I mean fellow players, "
                           f"{member.mention} doesn't have any boatbucks to take away. :slight_frown:")]
            else:
                # recipient has boatbucks but not as many as sender wants to take away
                if recipient.bucks < bucks:
                    replies = [(f"{member.mention} only has **{recipient.bucks}** {self.bbk}. "
                                f"I just took all of those from them instead. They now have exactly... **0** "
                                f"{self.bbk}. Poor sod.")]
                    session.delete(recipient)
                # default case sender takes as many or less boatbucks as recipient has
                else:
                    if recipient.bucks == bucks:
                        session.delete(recipient)
                        replies = [(f"First they took {member.mention}'s family and boatbucks, then they took their "
                                    f"health and their pride and finally they left them to die! "
                                    f"What will they do, when there's nothing left but to live or die?"),
                                   (f"{member.mention} has just been freed of the burden of owning boatbucks. "
                                    f"Who needs money anyway, right?"),
                                   (f"The boatbank giveth and the boatbank taketh away. "
                                    f"{member.mention} now has no more boatbucks.")]
                    else:
                        recipient.bucks -= bucks
                        replies = [(f"With pleasure boss. {member.mention} is now **{bucks}** "
                                    f"{self.bbk} poorer. They now have **{recipient.bucks}** "
                                    f"{self.bbk} left to pay for boatfacts, oars or bribes."),
                                   (f"Disintegrated **{bucks}** {self.bbk} from {member.mention}'s "
                                    f"account at the boatbank. They now have **{leftover}** left. "
                                    f"We're sorry but currency stability has to be ensured.")]
            session.commit()
        await ctx.send(random.choice(replies))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @take.error
    async def take_error(self, ctx, error):
        GlobalVars.set_value("caught", 1)
        if isinstance(error, commands.errors.MissingRequiredArgument):
            if error.param.name == "member":
                await ctx.send("You need to give me the name of the user you dummy!")
            elif error.param.name == "bucks":
                await ctx.send("While I'd love to take away other peoples hard earned boatbucks, "
                               "you need to tell me how many!")
        elif isinstance(error, commands.errors.BadArgument):
            await ctx.send(f"Sorry but who tf is **{error.argument}** supposed to be?")
        else:
            pe(error)
            logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")

def setup(bot):
    bot.add_cog(BBK(bot))
