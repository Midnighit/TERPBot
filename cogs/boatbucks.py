import random
from sqlalchemy import func
from discord import Member
from discord.ext import commands
from discord.ext.commands import group
from logger import logger
from config import PREFIX
from exiles_api import session, Boatbucks, Users, GlobalVars
from functions import pe, get_member

# rowboat birthday 25-July - potential reveal day?


class BBK(commands.Cog, name="Boatbucks commands."):
    def __init__(self, bot):
        self.bot = bot
        self.master_id = 440871726285324288
        self.permitted = [self.master_id, 221332467410403328, 136678918005456896]
        self.whitelisted = [190718422894641152]
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
                elif user.bucks < 0:
                    await ctx.send(f"You are {abs(user.bucks)} {self.bbk} in boatdebt. "
                                   f"Maybe you can earn some if you ask <@{self.master_id}> nicely!")
                else:
                    await ctx.send(f"You currently have {user.bucks} {self.bbk}. Don't spend them all in one place!")
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @boatbucks.command(help="Gives an overview of who has something, who's filthy rich and who has boatdebt.")
    async def list(self, ctx):
        if ctx.author.id in self.permitted:
            await ctx.send(("Alright boss, just give me a moment...\n"
                           f"*discreetely slides over a stack of papers to {str(ctx.author)[:-5]}*"))
            blocks = []
            positives, negatives, changed, delete = False, False, False, []
            for bbs in session.query(Boatbucks).order_by(Boatbucks.bucks.desc()).all():
                bucks, disc_id = bbs.bucks, bbs.id
                name = await get_member(ctx, disc_id)
                user = session.query(Users).filter_by(disc_id=disc_id).first()
                if not name:
                    if not user:
                        delete.append(disc_id)
                        continue
                    else:
                        name = user.disc_user
                else:
                    if str(name) != user.disc_user:
                        user.disc_user = str(name)
                        changed = True
                if changed:
                    session.commit()
                name = str(name)[:-5]

                if bucks == 0:
                    delete.append(disc_id)
                elif bucks > 0:
                    # if no headline for people with a positive amount of bbs has been posted
                    # yet, start a new block with that
                    if not positives:
                        block = "People with **boatbucks**:\n"
                        positives = True
                    add = f"{bucks} - {name}\n"
                    if len(block) + len(add) > 2000:
                        blocks.append(block)
                        block = add
                    else:
                        block += add
                else:
                    # if no headline for people with a negative amount of bbs has been posted
                    # yet, start a new block with that
                    if not negatives:
                        # if current block isn't empty, append it to blocks before starting a new one
                        if len(block) > 0:
                            blocks.append(block)
                        block = "People with **boatdebt**:\n"
                        negatives = True
                    add = f"{abs(bucks)} - {name}\n"
                    if len(block) + len(add) > 2000:
                        blocks.append(block)
                        block = add
                    else:
                        block += add
            if len(block) > 0:
                blocks.append(block)
            if len(blocks) == 0:
                await ctx.author.send(("It seems like nobody is using the boatback right now. Shame really. "
                                       "Maybe you need to distribute a few bucks to get the economy running."))
            else:
                for block in blocks:
                    await ctx.author.send(block)
            if len(delete) > 0:
                session.query(Boatbucks).filter(Boatbucks.id.in_(delete)).delete(synchronize_session='fetch')
                session.commit()
        else:
            await ctx.send(("Nope, no can do. The boatbank very much values the privacy of its customers...\n"
                            "most of the times...\nif it suits us..."))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @list.error
    async def list_error(self, ctx, error):
        GlobalVars.set_value("caught", 1)
        await ctx.send(
            "I'm terribly sorry but there has been an error, "
            "please contact support or ask my maker for help."
        )
        logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")

    @boatbucks.command(
        aliases=['pay'],
        help="Pay boatbucks to another player from your own account... or just print them if you own the boatbank."
    )
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
            # sender is in boatdebt
            if not sender or sender.bucks < 0:
                replies = [
                    (f"Nuh uh, you're already {abs(sender.bucks)} {self.bbk} in boatdebt. You can't pay what you "
                     f"don't have. Try to earn some boatbucks with <@{self.master_id}> or get someone with "
                     f"boatbucks to pay you first.")]
            elif not sender or sender.bucks < bucks:
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
                                f"It's your money. ¯\\_(ツ)_/¯"),
                               (f"Another **{bucks}** {self.bbk} further away from buying your own yacht. "
                                f"Maybe {member.mention} will be able to afford a rowboat after this transaction."),
                               (f"Feeling generous, huh? Very well your loss of **{bucks}** "
                                f"{self.bbk} will be {member.mention}'s gain.")]
                session.commit()
        await ctx.send(random.choice(replies))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @give.error
    async def give_error(self, ctx, error):
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

    @boatbucks.command(
        name="take",
        help=(
            "Withdraw a given amount of boatbucks from some poor soul. "
            "As befits such a tyrannical command, it's only available to Rowboat and her henchmen at the boatbank."
        )
    )
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
            if not recipient and bucks > 0:
                recipient = Boatbucks(id=member.id, bucks=0)
                session.add(recipient)
            if recipient.bucks == bucks:
                session.delete(recipient)
                replies = [(f"First they took {member.mention}'s family and boatbucks, then they took their "
                            f"health and their pride and finally they left them to die! "
                            f"What will they do, when there's nothing left but to live or die?"),
                           (f"{member.mention} has just been freed of the burden of owning boatbucks. "
                            f"Who needs money anyway, right?"),
                           (f"The boatbank giveth and the boatbank taketh away. "
                            f"{member.mention} now has no more boatbucks.")]
            elif recipient.bucks < bucks:
                recipient.bucks -= bucks
                replies = [(f"Huh, I guess you really don't like {member.mention}. Took {bucks} {self.bbk} from them "
                            f"They now have {abs(recipient.bucks)} {self.bbk} boatdebt."),
                           (f"Yet another person who's in boatdebt! Removed {bucks} {self.bbk} from {member.mention}. "
                            f"They now owe {abs(recipient.bucks)} {self.bbk} to the boatbank."),
                           (f"Hmm, I'm sure {member.mention} deserves it. Withdrew {bucks} {self.bbk} from them. They "
                            f"are now {abs(recipient.bucks)} {self.bbk} in boatdebt.")]
            else:
                recipient.bucks -= bucks
                replies = [(f"With pleasure boss. {member.mention} is now **{bucks}** "
                            f"{self.bbk} poorer. They now have **{recipient.bucks}** "
                            f"{self.bbk} left to pay for boatfacts, oars or bribes."),
                           (f"Disintegrated **{bucks}** {self.bbk} from {member.mention}'s "
                            f"account at the boatbank. They now have **{recipient.bucks}** left. "
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

    @boatbucks.command(
        name="tax",
        help=(
            "Withdraw funds to keep the boatbank afloat. "
            "Target of the tax is determined by a complicated algorithm that is totally not random."
        )
    )
    async def tax(self, ctx):
        # sender can't collect taxes
        if ctx.author.id not in self.permitted:
            replies = [(f"Trying to collect taxes on behalf of the boatbank? While that's very commendable only "
                        f"<@{self.master_id}> and her henchmen from the boatbank are allowed to collect taxes.")]
        else:
            filter = Boatbucks.bucks > 0, Boatbucks.id.notin_(self.whitelisted)
            recipients = session.query(Boatbucks).filter(*filter).all()
        if len(recipients) == 0:
            if session.query(func.count(Boatbucks.id)).scalar() == 0:
                replies = [("It looks like nobody has an open account on the boatbank yet. How comes?")]
            else:
                replies = [(f"It looks like nobody on the boatbanks has any {self.bbk} left to pay taxes with. "
                            "What gives?")]
        else:
            recipient, member = None, None
            while(not member and len(recipients) > 0):
                recipient = random.choice(recipients)
                member = await get_member(ctx, recipient.id)
                if not member:
                    recipients.remove(recipient)
            if member:
                recipient.bucks -= 1
                leftover = f"They now have {recipient.bucks} {self.bbk} left."
                replies = [(f"The taxboat cometh and has taken one {self.bbk} from {member.mention}! {leftover}"),
                           (f"You know what they say… nothing is certain but death and taxes. Removing one {self.bbk} "
                            f"from {member.mention}! {leftover}"),
                           (f"Yikes! Guess you should've hidden some of it in an 'offshore investment'… taking one "
                            f"{self.bbk} from {member.mention}! {leftover}")]
                session.commit()
            else:
                replies = [("Huh, looks like nobody who could afford a boattax is on this discord. "
                            "Sorry, but nothing I can do boss.")]
        await ctx.send(random.choice(replies))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    @tax.error
    async def tax_error(self, ctx, error):
        GlobalVars.set_value("caught", 1)
        pe(error)
        logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")


def setup(bot):
    bot.add_cog(BBK(bot))
