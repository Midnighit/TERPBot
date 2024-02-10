import random
from sqlalchemy import func
from discord import Member
from discord.ext import commands
from discord.ext.commands import group
from logger import logger
from config import PREFIX
from exiles_api import session, Dubloons, Users, GlobalVars
from functions import pe, get_member


class DBL(commands.Cog, name="Dubloons commands."):
    def __init__(self, bot):
        self.master_id = 327774595270705154
        self.permitted = [self.master_id, 221332467410403328]
        self.whitelisted = []
        self.dbl = "<:dubloon:1205498800265764915>"
        self.master = f"<@{self.master_id}>"
        self.bot = bot

    @group(aliases=["dubloon", "dbl"], help="Commands to pay and get paid with dubloons... if you're lucky.")
    async def dubloons(self, ctx):
        if ctx.author.id in self.permitted:
            if ctx.invoked_subcommand is None:
                await ctx.send(
                    "I have no idea what you want from me. I can either "
                    f"`{PREFIX}dubloons give <dubloons> <user>` or "
                    f"`{PREFIX}dubloons take <dubloons> <user>` for you."
                )
        else:
            if ctx.invoked_subcommand is None:
                user = session.query(Dubloons).get(ctx.author.id)
                if user is None or user.dubloons == 0:
                    replies = [
                        (
                            f"You don't have any {self.dbl}. "
                            f"Maybe you can earn some if you ask {self.master} nicely!"
                        ),
                        (
                            f"Hold on, let me check those pockets... Nope, nothin' but lint in there. "
                            f"No {self.dbl} for you! Time to get to work! "
                            f"Or you can appeal to {self.master}'s generosity, but don't be too annoying."
                        ),
                        (
                            f"Your Dubloonery account balance is lookin' a bit bleak! "
                            f"Better start scheming up some ways to earn those {self.dbl}."
                        ),
                        (
                            "Uh oh! Seems like the dubloon well has run dry for you. "
                            "Maybe try shaking some loose from those pesky sofa cushions?"
                        ),
                        (
                            "Your dubloon count rivals the emptiness of space. "
                            "But hey, it can only go up from here, right?"
                        ),
                        (
                            "I'm afraid your dubloon reserves are about as plentiful as a unicorn sighting. "
                            "Best get busy earning!"
                        ),
                        (
                            "Uh-oh, did a dubloon pirate plunder your stash? "
                            "Better set sail on a treasure hunt to restock!"
                        ),
                        (
                            "Ahem. It seems you're currently experiencing a...  dubloon drought. "
                            "Have you considered offering your services around the Dubloonery?"
                        ),
                        (
                            f"You are broke. You have zero {self.dbl} in your account. "
                            f"Maybe you should stop gambling or wasting your {self.dbl} on useless things. "
                            f"Or you can ask {self.master} for a dubloan."
                        ),
                        (
                            f"You have nothing. Nada. Zilch. Zip. No {self.dbl} for you. "
                            f"Maybe you should work harder or smarter to get some {self.dbl}. "
                            f"Or you can beg {self.master} for some charity, but don't expect much."
                        )
                    ]
                    await ctx.send(random.choice(replies))
                elif user.dubloons < 0:
                    replies = [
                        (
                            f"You are {abs(user.dubloons)} {self.dbl} in dubdebt. "
                            f"Maybe you can earn some if you ask {self.master} nicely!"
                        ),
                        (
                            f"Your dubloon balance is currently showing a dubficit of {abs(user.dubloons)} {self.dbl}. "
                            f"Time to start selling seashells!"
                        ),
                        (
                            f"Whoops! You're swimming in dubdebt to the tune of {abs(user.dubloons)} {self.dbl}. "
                            f"Better watch out for {self.master}'s loan sharks…"
                        ),
                        (
                            f"Your dubloon balance is deeper in the negatives than a sunken pirate ship - "
                            f"{abs(user.dubloons)} {self.dbl} to be exact! "
                            f"Might want to start doing some chores for {self.master}..."
                        ),
                        (
                            f"Your dubloon debt is at {abs(user.dubloons)} {self.dbl}. "
                            "That's what we call a dub-le whammy!"
                        ),
                        (
                            f"Your dubdebt is {abs(user.dubloons)} {self.dbl}. That's a dubacle. "
                            f"Maybe you can ask {self.master} for a dubloan, "
                            f"but be prepared to pay a high interest rate."
                        ),
                        (
                            f"Your dubloon balance is {abs(user.dubloons)} {self.dbl} in the red. That's a dub-ious "
                            f"situation. You might want to seek some financial advice from {self.master} or "
                            f"one of her henchmen."
                        ),
                        (
                            f"You owe {abs(user.dubloons)} {self.dbl} to the Dubloonery. That's a lot of dubloons. "
                            f"Maybe you can work out a deal with {self.master} or find some hidden treasure."
                        ),
                        (
                            f"Your dubloon balance is {abs(user.dubloons)} {self.dbl} in the negative. You might want "
                            f"to look for some alternative sources of income or ask {self.master} for a bailout."
                        )
                    ]
                    await ctx.send(random.choice(replies))
                else:
                    replies = [
                        f"You currently have {user.dubloons} {self.dbl}. Don't spend them all in one place!",
                        (
                            f"{user.dubloons} {self.dbl} and counting! Maybe {self.master} "
                            f"will offer you a loyalty bonus... or send her henchmen to 'collect' a fee..."
                        ),
                        (
                            f"The Dubloonery ledger shows a balance of {user.dubloons} {self.dbl}. "
                            f"Looks like you're doing something right!"
                        ),
                        (
                            f"With {user.dubloons} {self.dbl}, the possibilities are endless! "
                            f"Maybe even a bribe for {self.master}?"
                        ),
                        (
                            f"Your dubloon pouch clinks with the weight of {user.dubloons} {self.dbl}. "
                            f"Spend wisely, or pay the price!"
                        ),
                        (
                            f"{user.dubloons} {self.dbl}... even those loyal to {self.master} and her henchmen "
                            f"get the occasional 'audit'."
                        ),
                        (
                            f"Your coffers hold {user.dubloons} {self.dbl}. Now get back to work for {self.master}... "
                            f"those dubloons won't earn themselves!"
                        ),
                        (
                            f"{user.dubloons} {self.dbl}? That's a fine start, but don't rest on your laurels. "
                            f"Remember, {self.master} always keeps an eye on her riches."
                        ),
                        (
                            f"{user.dubloons} {self.dbl}? Not bad, but don't get too comfortable. "
                            f"In the Dubloonery, fortunes can change on a whim."
                        ),
                        (
                            f"With {user.dubloons} {self.dbl} at your disposal, you're ready for anything... "
                            f"well, almost anything. Don't forget who's boss!"
                        )
                    ]
                    await ctx.send(random.choice(replies))
        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

    # list command
    @dubloons.command(help="Gives an overview of who has something, who's filthy rich and who has dubdebt.")
    async def list(self, ctx):
        if ctx.author.id in self.permitted:
            await ctx.send(
                (
                    "Alright boss, just give me a moment...\n"
                    f"*discreetely slides over a stack of papers to {str(ctx.author)[:-6]}*"
                )
            )
            blocks, block = [], ''
            positives, negatives, changed, delete = False, False, False, []
            for dbl in session.query(Dubloons).order_by(Dubloons.dubloons.desc()).all():
                dubloons, disc_id = dbl.dubloons, dbl.id
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

                if dubloons == 0:
                    delete.append(disc_id)
                elif dubloons > 0:
                    # if no headline for people with a positive amount of bbs has been posted
                    # yet, start a new block with that
                    if not positives:
                        block = "People with **dubloons**:\n"
                        positives = True
                    add = f"{dubloons} - {name}\n"
                    if len(block) + len(add) > 1800:
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
                        block = "People with **dubdebt**:\n"
                        negatives = True
                    add = f"{abs(dubloons)} - {name}\n"
                    if len(block) + len(add) > 1800:
                        blocks.append(block)
                        block = add
                    else:
                        block += add
            if len(block) > 0:
                blocks.append(block)
            if len(blocks) == 0:
                await ctx.author.send(
                    (
                        "It seems like nobody is using the Dubloonery right now. Shame really. "
                        "Maybe you need to distribute a few dubloons to get the economy running."
                    )
                )
            else:
                for block in blocks:
                    await ctx.author.send(block)
            if len(delete) > 0:
                session.query(Dubloons).filter(Dubloons.id.in_(delete)).delete(synchronize_session="fetch")
                session.commit()
        else:
            await ctx.send(
                (
                    "Nope, no can do. The Dubloonery very much values the privacy of its customers...\n"
                    "most of the times...\nif it suits us..."
                )
            )

    @list.error
    async def list_error(self, ctx, error):
        GlobalVars.set_value("CAUGHT", 1)
        await ctx.send(
            "I'm terribly sorry but there has been an error, " "please contact support or ask my maker for help."
        )
        logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")

    # give command
    @dubloons.command(
        aliases=["pay"],
        help="Pay dubloons to another player from your own account... or just print them if you own the Dubloonery.",
    )
    async def give(self, ctx, dubloons: int, member: Member):
        # sender tries to send a negative amount of dubloons (i.e. gaining dubloons)
        if dubloons < 0:
            replies = ["Ok, I get it. It was fun while it lasted but no more giving of negative amounts anymore!"]
        # sender and recipient of the dubloons are the same person
        elif ctx.author.id == member.id:
            replies = [
                (
                    "Trying to send dubloons to yourself, huh? "
                    "You think you're very clever don't you? Sorry, but no dice!"
                )
            ]
        # both sender and recipient are able to create and take away dubloons at will
        elif ctx.author.id in self.permitted and member.id in self.permitted:
            replies = [f"Oh c'mon. You known that {member.mention} already has unlimited credit with the Dubloonery!"]
        # sender can create and take away dubloons at will
        elif ctx.author.id in self.permitted:
            recipient = session.query(Dubloons).get(member.id)
            if not recipient:
                recipient = Dubloons(id=member.id, dubloons=dubloons)
                session.add(recipient)
            else:
                recipient.dubloons += dubloons
            session.commit()
            replies = [
                (
                    f"Sure boss. Created **{dubloons}** {self.dbl} out of thin air for {member.mention}. "
                    f"I hope you know what you're doing..."
                ),
                (
                    f"Here I am, brain the size of a planet, and they tell me to give {member.mention} **{dubloons}** "
                    f"{self.dbl}. Call that job satisfaction? 'Cos I don't."
                ),
                (
                    f"Are you sure {member.mention} really deserves it? Fine, fine transferring **{dubloons}** "
                    f"{self.dbl} to their account. _dramatic sigh_"
                ),
                (
                    f"Firing up the money minting machine. **{dubloons}** "
                    f"{self.dbl} for {member.mention} coming right up!"
                ),
                (
                    f"Wow, you're feeling generous today. Giving {member.mention} {dubloons} "
                    f"{self.dbl} just like that. Don't you worry about inflation?"
                ),
                (
                    f"Alright, alright. I'll do as you say. Adding {dubloons} "
                    f"{self.dbl} to {member.mention}'s account. But don't blame me if they get greedy."
                ),
                (
                    f"Fine, fine. I'll give {member.mention} {dubloons} "
                    f"{self.dbl}. But you know what they say: easy come, easy go."
                ),
                (
                    f"{member.mention} better spend those {dubloons} {self.dbl} wisely. "
                    "You know, 'a dubloon saved is a dubloon earned'."
                ),
                (
                    f"Consider it a dubloon stimulus package. {member.mention} is {dubloons} {self.dbl} "
                    "richer. Let's see what they do with it!"
                ),
                (
                    f"Oh, you want to give {member.mention} {dubloons} "
                    f"{self.dbl}? Sure, sure. It's not like I have anything better to do."
                ),
                (
                    f"Wow, {member.mention} must have done something really impressive to earn {dubloons} "
                    f"{self.dbl} from you. Or maybe you just like them a lot. Either way, it's done."
                ),
                (
                    f"OK, OK. I'll give {member.mention} {dubloons} "
                    f"{self.dbl}. But you know, money can't buy happiness. Unless you spend it on me, of course."
                )
            ]
        else:
            sender = session.query(Dubloons).get(ctx.author.id)
            # sender is in dubdebt
            if not sender or sender.dubloons < 0:
                replies = [
                    (
                        f"Nuh uh, you're already {abs(sender.dubloons)} {self.dbl} in dubdebt. You can't pay what you "
                        f"don't have. Try to earn some dubloons with {self.master} or get someone with "
                        f"dubloons to pay you first."
                    ),
                    (
                        f"Sorry, but you can't give {dubloons} {self.dbl} to {member.mention} when you owe "
                        f"{abs(sender.dubloons)} {self.dbl} to the Dubloonery. Maybe you should stop spending "
                        f"your dubloons on useless things like clothes and food."
                    ),
                    (
                        f"Nice try, but you can't fool the Dubloonery. You have {abs(sender.dubloons)} {self.dbl} "
                        f"of dubdebt, so you can't afford to pay {dubloons} {self.dbl} to {member.mention}. "
                        f"Maybe you should ask {self.master} for a loan… or a mercy kill."
                    ),
                    (
                        f"Wow, you're really generous… or really stupid. You can't give away {dubloons} {self.dbl} "
                        f"when you're {abs(sender.dubloons)} {self.dbl} in the red. How about you work on "
                        f"clearing your dubdebt first, before you go around playing Santa Claus?"
                    ),
                    (
                        f"Are you kidding me? You have {abs(sender.dubloons)} {self.dbl} of dubdebt, and you want "
                        f"to give {dubloons} {self.dbl} to {member.mention}? Do you think this is a charity? "
                        f"Get your priorities straight, and pay your dues to the Dubloonery first."
                    ),
                    (
                        f"Hey, don't be a dubloon-digger. You can't pay {dubloons} {self.dbl} to {member.mention} "
                        f"when you're {abs(sender.dubloons)} {self.dbl} in dubdebt. You need to earn your own "
                        f"dubloons, not leech off others. Go do some quests, or sell some loot, or rob some "
                        f"villagers. Anything but this."
                    ),
                    (
                        f"Sorry, but you can't make it rain {dubloons} {self.dbl} on {member.mention} when you're "
                        f"{abs(sender.dubloons)} {self.dbl} in dubdebt. You need to save your dubloons, not "
                        f"squander them. Maybe you should take some financial advice from {self.master}, or "
                        f"one of her henchmen. They know how to handle (or create) money."
                    ),
                    (
                        f"Oops, you can't transfer {dubloons} {self.dbl} to {member.mention} when you have "
                        f"{abs(sender.dubloons)} {self.dbl} of dubdebt. You need to pay your bills, not your "
                        f"friends. Maybe you should cut down on your expenses, like those fancy weapons and "
                        f"armors you keep buying. They're not worth it."
                    ),
                    (
                        f"Nope, you can't donate {dubloons} {self.dbl} to {member.mention} when you're "
                        f"{abs(sender.dubloons)} {self.dbl} in dubdebt. You need to take care of yourself, not "
                        f"others. Maybe you should invest your dubloons in something profitable, like a "
                        f"business or a trade. Or just gamble them away, that works too."
                    ),
                    (
                        f"You wanna give {dubloons} {self.dbl}? Bold move, considering you're {abs(sender.dubloons)} "
                        f"{self.dbl} in the hole. Maybe {self.master} will offer you a high-interest loan?"
                    )
                ]
            elif not sender or sender.dubloons < dubloons:
                # sender has no dubloons at all
                if not sender or sender.dubloons == 0:
                    replies = [
                        (
                            f"You don't have a single penny, much less a whole dubloon right now. "
                            f"Try earning some dubloons with {self.master} first!"
                        ),
                        (
                            "Sorry, but you can't give what you don't have. You have **zero** dubloons on your "
                            "account. Maybe you should stop spending them on useless things like clothes and food."
                        ),
                        (
                            "Nice try, but you can't fool the Dubloonery. You have no dubloons to give or pay anyone. "
                            "You should be more careful with your finances, or you'll end up in dubdebt."
                        ),
                        (
                            f"Are you kidding me? You have zero dubloons on your account. You can't give or pay anyone "
                            f"with thin air. Maybe you should ask {self.master} for a dubloan, "
                            f"or sell some of your organs on the black market."
                        ),
                        (
                            f"Oops, you have a problem. You have no dubloons on your account. "
                            f"You can't give or pay anyone with that. "
                            f"Maybe you should work harder for {self.master}, or rob some other players."
                        ),
                        (
                            f"Ha ha, very funny. You have zero dubloons on your account. "
                            f"You can't give or pay anyone with that. Maybe you should learn some useful skills "
                            f"from {self.master}, or gamble some of your items in the casino."
                        ),
                        (
                            f"Sorry to burst your bubble, but you have no dubloons on your account. "
                            f"You can't give or pay anyone with that. Maybe you should beg for some dubloons "
                            f"from {self.master}, or trade some of your secrets in the dark web."
                        ),
                        (
                            f"Ouch, that's embarrassing. You have no dubloons on your account. "
                            f"You can't give or pay anyone with that. Maybe you should borrow some dubloons from "
                            f"{self.master}, or sell some of your nudes in the chat."
                        ),
                        (
                            "Wow, you have zero dubloons on your account. You can't give or pay anyone with that. "
                            "Maybe you should sacrifice some of your slaves in the altar and hope for the best."
                        ),
                        (
                            f"Oops, you have no dubloons on your account. You can't give or pay anyone with that. "
                            f"Maybe you do some dirty work for {self.master} to earn some."
                        )
                    ]
                # sender doesn't have as many dubloons as they want to send
                else:
                    replies = [
                        (
                            f"Nice try but you only have **{sender.dubloons}** {self.dbl}. "
                            f"Try to earn some with {self.master} first!"
                        ),
                        (
                            f"Ah, the ol' 'Ponzi Scheme'—bold move! But with just **{sender.dubloons}** {self.dbl} in "
                            f"your coffers, you're more like a 'Bernie Madoff.' Keep dreaming of that "
                            f"pyramid-shaped mansion!"
                        ),
                        (
                            f"Wow, {ctx.author.mention}, you're such a big spender. Too bad you only have "
                            f"{sender.dubloons} {self.dbl} in your pocket. Maybe you should rob a bank or something. "
                            f"Oh wait, you can't, because {self.master} owns the only bank in town. And she doesn't "
                            f"like competition."
                        ),
                        (
                            f"Whoa there, {ctx.author.mention}, you're not in dubdebt yet, but with only "
                            f"**{sender.dubloons}** {self.dbl} and your current spending habits, you're on a one-way "
                            f"trip!"
                        ),
                        (
                            f"Hey {ctx.author.mention}, your generosity is commendable, but your math... not so much. "
                            f"You only have **{sender.dubloons}** {self.dbl}. Maybe it's time for a reality check?"
                        ),
                        (
                            f"Ha ha ha, that's hilarious, {ctx.author.mention}. You want to give away more dubloons "
                            f"than you have? You only have {sender.dubloons} {self.dbl}, you know. That's like trying "
                            f"to give away more blood than you have. You'll end up dead, or worse, in dubdebt. "
                            f"Don't be silly, be smart."
                        ),
                        (
                            f"Are you serious, {ctx.author.mention}? You only have {sender.dubloons} {self.dbl} and "
                            f"you want to give away more? That's like trying to give away more oxygen than you have. "
                            f"You'll suffocate, or worse, end up in dubdebt. Don't be stupid, be wise."
                        ),
                        (
                            f"Come on, {ctx.author.mention}, don't be ridiculous. You only have {sender.dubloons} "
                            f"{self.dbl} and you want to give away more? That's like trying to give away more brain "
                            f"cells than you have. You'll go insane, or worse, end up in dubdebt. "
                            f"Don't be crazy, be sane."
                        ),
                        (
                            f"Really, {ctx.author.mention}? You only have {sender.dubloons} {self.dbl} and you want to "
                            f"give away more? That's like trying to give away more limbs than you have. "
                            f"You'll be crippled, or worse, end up in dubdebt. Don't be reckless, be careful."
                        )
                    ]
            else:
                sender.dubloons -= dubloons
                # recipient can create and take away dubloons at will
                if member.id in self.permitted:
                    replies = [
                        (
                            f"Destroying **{dubloons}** {self.dbl} for you. "
                            f"{member.mention} doesn't need them anyway."
                        ),
                        (
                            f"Sure, let's fight inflation and remove **{dubloons}** {self.dbl} from circulation. "
                            f"{member.mention} has unlimited credit at the Dubloonery anyway."
                        ),
                        (
                            f"**{dubloons}** {self.dbl} have been removed from the economy. "
                            f"{member.mention}, let's hope your generosity isn't causing a recession!"
                        ),
                        (
                            f"**{dubloons}** {self.dbl} have been removed. "
                            f"{member.mention}, you're the Dubloonery's own Thanos!"
                        ),
                        (
                            f"**{dubloons}** {self.dbl} donated to the void! No take-backs, {member.mention}."
                        ),
                        (
                            f"Into the abyss go **{dubloons}** {self.dbl}. "
                            f"We appreciate your contribution to the dubloon black hole, {member.mention}"
                        ),
                        (
                            f"Poof! **{dubloons}** {self.dbl} have disappeared. "
                            f"Perhaps a dubloon goblin got them, {member.mention}?"
                        ),
                        (
                            f"**{dubloons}** {self.dbl} have been incinerated. "
                            f"Praise {member.mention} for making all the remaing ones more valuable."
                        ),
                        (
                            f"Your offering of **{dubloons}** {self.dbl} has been accepted. "
                            f"Eldubya may or may not use them... who knows?"
                        ),
                        (
                            f"**{dubloons}** {self.dbl} have been fed to the treasury sea monster. "
                            f"It appreciates your sacrifice, {member.mention}."
                        )
                    ]
                # default case sender and recipient are normal and sender has enough dubloons
                else:
                    recipient = session.query(Dubloons).get(member.id)
                    if not recipient:
                        recipient = Dubloons(id=member.id, dubloons=dubloons)
                        session.add(recipient)
                    else:
                        recipient.dubloons += dubloons
                    replies = [
                        (
                            f"Alright, transferring **{dubloons}** {self.dbl} from your account to {member.mention}. "
                            f"It's your money. ¯\\_(ツ)_/¯"
                        ),
                        (
                            f"Feeling generous, huh? Very well your loss of **{dubloons}** "
                            f"{self.dbl} will be {member.mention}'s gain."
                        ),
                        (
                            f"**{dubloons}** {self.dbl} have been taken from your account and "
                            f"given to {member.mention}. Don't come crying to {self.master} when you're broke!"
                        ),
                        (
                            f"**{dubloons}** {self.dbl} have been moved from your account to {member.mention}'s. "
                            f"{self.master} thanks you for your generous donation to the 'Help a Friend' fund."
                        ),
                        (
                            f"**{dubloons}** {self.dbl} have been transferred from your account to {member.mention}'s. "
                            f"Just remember, in the game of dubloons, you win or you go into dubdebt!"
                        ),
                        (
                            f"Hope you weren't too attached to those **{dubloons}** {self.dbl}. "
                            f"They're enjoying a new life in {member.mention}'s pocket now."
                        ),
                        (
                            f"Transaction complete! Your bank balance is a little lighter ({dubloons} {self.dbl} to "
                            f"be exact), but {member.mention} is feeling flush. Enjoy responsibly, you two!"
                        ),
                        (
                            f"Are you sure about this, {ctx.author.mention}? {member.mention} might use those "
                            f"**{dubloons}** {self.dbl} to rise up and overthrow you. "
                            f"Dubloon-funded revolutions are all the rage."
                        ),
                        (
                            f"The Dubloonery thanks you for facilitating this transfer of **{dubloons}** {self.dbl} "
                            f"from {ctx.author.mention} to {member.mention}."
                        )
                    ]
                session.commit()
        await ctx.send(random.choice(replies))

    @give.error
    async def give_error(self, ctx, error):
        GlobalVars.set_value("CAUGHT", 1)
        if isinstance(error, commands.errors.MissingRequiredArgument):
            if error.param.name == "member":
                await ctx.send("You need to give me the name of the user you dummy!")
            elif error.param.name == "dubloons":
                await ctx.send("Soooo just _how_ many dubloons am I supposed to give?")
        elif isinstance(error, commands.errors.BadArgument):
            await ctx.send(f"Sorry but who tf is **{error.argument}** supposed to be?")
        elif isinstance(error, ValueError):
            await ctx.send("You need to pay in dubloons not in members dummy!")
        else:
            pe(error)
            logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")

    # take command
    @dubloons.command(
        name="take",
        help=(
            "Withdraw a given amount of dubloons from some poor soul. "
            "As befits such a tyrannical command, it's only available to "
            "Eldubya and her henchmen at the Dubloonery."
        ),
    )
    async def take(self, ctx, dubloons: int, member: Member):
        # sender can't create and take away dubloons at will
        if ctx.author.id not in self.permitted:
            replies = [
                (
                    f"No can do. Only {self.master} and her henchmen from the Dubloonery are allowed to  "
                    f"take other peoples dubloons without asking for permission. "
                    f"Sorry mate, the world just ain't fair."
                ),
                (
                    f"Hey, you can't just take {self.dbl} from others. "
                    f"That privilege is reserved for {self.master} and her henchmen. Nice try though!"
                ),
                (
                    f"Listen up, messing with {self.dbl} is {self.master}'s territory. Maybe try being less "
                    f"*ambitious* and more focused on, ya know, not getting eaten by those giant spiders..."
                )
            ]
        # recipient can create and take away dubloons at will
        elif member.id in self.permitted:
            replies = [
                (
                    "Hey, you can't take away dubloons from a fellow employee at the Dubloonery. "
                    "You may have to talk to Midnight if you want to have them fired for good."
                ),
                (
                    "Listen, my hands are already dirty enough with all this dubious dubloon dealing. "
                    "Don't make me add you to the list."
                ),
                (
                    "Ah, internal power struggles - a classic sign of a thriving criminal enterprise. "
                    "Keep trying to undermine each other, maybe Midnight will reward the last one standing!"
                )
            ]
        else:
            recipient = session.query(Dubloons).get(member.id)
            if not recipient and dubloons != 0:
                recipient = Dubloons(id=member.id, dubloons=0)
                session.add(recipient)
            if recipient.dubloons == dubloons:
                session.delete(recipient)
                replies = [
                    (
                        f"First they took {member.mention}'s family and dubloons, then they took their "
                        f"health and their pride and finally they left them to die! "
                        f"What will they do, when there's nothing left but to live or die?"
                    ),
                    (
                        f"{member.mention} has just been freed of the burden of owning dubloons. "
                        f"Who needs money anyway, right?"
                    ),
                    (
                        f"The Dubloonery giveth and the Dubloonery taketh away. "
                        f"{member.mention} now has no more dubloons."
                    ),
                    (
                        f"Took away all of {member.mention}'s {self.dbl}."
                        f"Remember – those with less to lose often fight the hardest."
                        f"Think of those extracted {self.dbl} as a donation to the cause of survival!"
                    ),
                    (
                        f"{member.mention}, it is said that with great wealth comes great "
                        f"responsibility. Now, at last, you are responsibility-free!"
                    ),
                    (
                        f"Let's play a little game called 'Zero Dubloons'. And guess what? "
                        f"{member.mention} just won!"
                    ),
                    (
                        f"In the realm of dubloons, zero is the new black. {member.mention} just "
                        f"embraced the latest fashion trend."
                    ),
                    (
                        f"Breaking news: {member.mention} achieves absolute zen by attaining "
                        f"dubloon equilibrium. Zero dubloons, zero worries!"
                    )
                ]
            elif recipient.dubloons < dubloons:
                recipient.dubloons -= dubloons
                replies = [
                    (
                        f"Huh, I guess you really don't like {member.mention}. Took {dubloons} {self.dbl} from them "
                        f"They now have {abs(recipient.dubloons)} {self.dbl} dubdebt."
                    ),
                    (
                        f"Yet another person who's in dubdebt! Removed {dubloons} {self.dbl} from {member.mention}. "
                        f"They now owe {abs(recipient.dubloons)} {self.dbl} to the Dubloonery."
                    ),
                    (
                        f"Hmm, I'm sure {member.mention} deserves it. Withdrew {dubloons} {self.dbl} from them. They "
                        f"are now {abs(recipient.dubloons)} {self.dbl} in dubdebt."
                    ),
                    (
                        f"{member.mention}'s balance just took a nasty tumble. Yoinked {dubloons} {self.dbl}, and now "
                        f"they're down a whopping {abs(recipient.dubloons)} {self.dbl}. Enjoy the dubdebt!"
                    ),
                    (
                        f"{ctx.author.mention}, ruthless as always! You swiped {dubloons} {self.dbl} from "
                        f"{member.mention}. Don't expect them to pay anytime soon...they're swimming in "
                        f"{abs(recipient.dubloons)} {self.dbl} worth of dubdebt."
                    ),
                    (
                        f"Looks like {ctx.author.mention} is feeling generous...with someone else's dubloons! Took "
                        f"{dubloons} {self.dbl} from {member.mention}. Now they're drowning in "
                        f"{abs(recipient.dubloons)} {self.dbl} of dubdebt."
                    ),
                    (
                        f"Oh, {ctx.author.mention} playing the role of the debt collector again? Extracted {dubloons} "
                        f"{self.dbl} from {member.mention}. They're now in a deep hole of {abs(recipient.dubloons)} "
                        f"{self.dbl} dubdebt."
                    ),
                    (
                        f"Looks like {ctx.author.mention} is auditing accounts today! Just docked {dubloons} "
                        f"{self.dbl} from {member.mention}. Now they're sitting at {abs(recipient.dubloons)} "
                        f"{self.dbl} in dubdebt. Yikes!"
                    ),
                    (
                        f"{ctx.author.mention} strikes with surgical precision, relieving {member.mention} of "
                        f"{dubloons} {self.dbl}. Now they're staring at {abs(recipient.dubloons)} {self.dbl} worth of "
                        f"dubdebt, courtesy of the Dubloonery."
                    )
                ]
            else:
                recipient.dubloons -= dubloons
                replies = [
                    (
                        f"With pleasure boss. {member.mention} is now **{dubloons}** "
                        f"{self.dbl} poorer. They now have **{recipient.dubloons}** "
                        f"{self.dbl} left to pay for favours or bribe {self.master}."
                    ),
                    (
                        f"Disintegrated **{dubloons}** {self.dbl} from {member.mention}'s "
                        f"account at the Dubloonery. They now have **{recipient.dubloons}** left. "
                        f"We're sorry but currency stability has to be ensured."
                    ),
                    (
                        f"Let's call it an... administrative fee. {member.mention}, **{dubloons}** "
                        f"{self.dbl} have magically vanished. Poof! You're left with a tidy "
                        f"sum of **{recipient.dubloons}** {self.dbl}."
                    ),
                    (
                        f"Whoops, there go **{dubloons}** {self.dbl}, {member.mention}. An unfortunate "
                        f"clerical error, shall we say? Oh well, you still have **{recipient.dubloons}** "
                        f"{self.dbl} remaining."
                    ),
                    (
                        f"The Dubloonery thanks you for your involuntary contribution of **{dubloons}** "
                        f"{self.dbl}, {member.mention}. Don't fret, you have **{recipient.dubloons}** "
                        f"{self.dbl} to console yourself."
                    ),
                    (
                        f"Looks like {member.mention} just incurred a processing fee of **{dubloons}** "
                        f"{self.dbl}. The things we do for customer service, folks! "
                        f"Account balance stands at **{recipient.dubloons}** {self.dbl}."
                    ),
                    (
                        f"Consider those **{dubloons}** {self.dbl} a little surcharge "
                        f"{member.mention}. Nothing personal... Much. You're still left with "
                        f"**{recipient.dubloons}** {self.dbl}."
                    ),
                    (
                        f"Well, well, well, {member.mention}. Looks like you've just lost **{dubloons}** "
                        f"{self.dbl}. Fear not, you're not completely bankrupt yet. You still have "
                        f"**{recipient.dubloons}** {self.dbl} to your name."
                    ),
                    (
                        f"A pinch here, a pinch there, and voilà, {member.mention} has just lost "
                        f"**{dubloons}** {self.dbl}. But hey, you're not destitute yet! You still "
                        f"have **{recipient.dubloons}** {self.dbl} to your name."
                    ),
                    (
                        f"{member.mention}, you've just experienced a slight shrinkage in your account "
                        f"by **{dubloons}** {self.dbl}. Not to worry, you're still hanging onto "
                        f"**{recipient.dubloons}** {self.dbl}."
                    ),
                    (
                        f"Looks like we've just skimmed off the top of {member.mention}'s account. "
                        f"**{dubloons}** {self.dbl} less now. But fret not, you're still in the "
                        f"black with **{recipient.dubloons}** {self.dbl}."
                    ),
                    (
                        f"{member.mention}, you've just experienced a little financial trim. **{dubloons}** "
                        f"{self.dbl} less, but hey, you still have **{recipient.dubloons}** {self.dbl} "
                        f"to play with."
                    ),
                    (
                        f"A slight adjustment to {member.mention}'s account, **{dubloons}** {self.dbl} "
                        f"lighter. But don't despair, you're left with **{recipient.dubloons}** "
                        f"{self.dbl}. Spend it wisely!"
                    ),
                    (
                        f"{member.mention}, it seems you've just had a nibble taken out of your account. "
                        f"**{dubloons}** {self.dbl} less, but you're still hanging onto "
                        f"**{recipient.dubloons}** {self.dbl}."
                    ),
                    (
                        f"A gentle subtraction from {member.mention}'s account, **{dubloons}** {self.dbl} "
                        f"less. Don't fret, you still have **{recipient.dubloons}** {self.dbl} "
                        f"to spare."
                    )
                ]
            session.commit()
        await ctx.send(random.choice(replies))

    @take.error
    async def take_error(self, ctx, error):
        GlobalVars.set_value("CAUGHT", 1)
        if isinstance(error, commands.errors.MissingRequiredArgument):
            if error.param.name == "member":
                await ctx.send("You need to give me the name of the user you dummy!")
            elif error.param.name == "dubloons":
                await ctx.send(
                    "While I'd love to take away other peoples hard earned dubloons, " "you need to tell me how many!"
                )
        elif isinstance(error, commands.errors.BadArgument):
            await ctx.send(f"Sorry but who tf is **{error.argument}** supposed to be?")
        elif isinstance(error, ValueError):
            await ctx.send("You need to take dubloons not members dummy!")
        else:
            pe(error)
            logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")

    # tax command
    @dubloons.command(
        name="tax",
        help=(
            "Withdraw funds to keep the Dubloonery afloat. "
            "Target of the tax is determined by a complicated algorithm that is totally not random."
        ),
    )
    async def tax(self, ctx, dubloons: int = 1):
        # sender can't collect taxes
        if ctx.author.id not in self.permitted:
            replies = [
                (
                    f"Trying to collect taxes on behalf of the Dubloonery? While that's very commendable only "
                    f"{self.master} and her henchmen from the Dubloonery are allowed to collect taxes."
                ),
                (
                    f"You wouldn't happen to have a warrant signed by {self.master} authorizing these tax "
                    f"collections' , would you? No? Didn't think so."
                ),
                (
                    "Perhaps some lessons in dubloonomics are in order. It seems you're unfamiliar with the "
                    "complex socioeconomic structure of the Dubloonery.",
                ),
                (
                    f"{ctx.author.mention}, the only thing taxing here is your attempt to levy dubloons without "
                    f"{self.master}'s approval."
                ),
                (
                    f"{ctx.author.mention}, attempting to enact fiscal policy without {self.master}'s consent? "
                    f"That's a paddlin'."
                )
            ]
        else:
            filter = Dubloons.dubloons >= dubloons, Dubloons.id.notin_(self.whitelisted)
            recipients = session.query(Dubloons).filter(*filter).all()
        if len(recipients) == 0:
            if session.query(func.count(Dubloons.id)).scalar() == 0:
                replies = ["It looks like nobody has an open account on the Dubloonery yet. How comes?"]
            else:
                replies = [
                    f"It looks like nobody on the Dubloonerys has enough {self.dbl} left to pay taxes with. What gives?"
                ]
        else:
            recipient, member = None, None
            while not member and len(recipients) > 0:
                recipient = random.choice(recipients)
                member = await get_member(ctx, recipient.id)
                if not member:
                    recipients.remove(recipient)
            if member:
                recipient.dubloons -= dubloons
                replies = [
                    (
                        f"The taxman cometh and has taken {dubloons} {self.dbl} from {member.mention}! They now have "
                        f"{recipient.dubloons} {self.dbl} left."
                    ),
                    (
                        f"You know what they say… nothing is certain but death and taxes. Removing {dubloons} "
                        f"{self.dbl} from {member.mention}! They now have {recipient.dubloons} {self.dbl} left."
                    ),
                    (
                        f"Yikes! Guess you should've hidden some of it in an 'offshore investment'… taking {dubloons} "
                        f"{self.dbl} from {member.mention}! They now have {recipient.dubloons} {self.dbl} left."
                    ),
                    (
                        f"Who needs welfare when you can have taxation, right? Snagged {dubloons} {self.dbl} from "
                        f"{member.mention}. They've got {recipient.dubloons} {self.dbl} left. Hope they can buy "
                        f"instant noodles..."
                    ),
                    (
                        f"It's just _business_, {member.mention}. Nothing personal. Well, okay, maybe a little "
                        f"personal. Oh well, those {dubloons} {self.dbl} will look great in our accounts! "
                        f"You now have {recipient.dubloons} {self.dbl}."
                    ),
                    (
                        f"{member.mention}, those {dubloons} {self.dbl} weren't going to spend themselves, "
                        f"right? Consider it a... donation to the Dubloonery Expansion Fund! They now have "
                        f"{recipient.dubloons} {self.dbl} left."
                    ),
                    (
                        f"Just another day serving the glorious Dubloonery! Those {dubloons} {self.dbl} will "
                        f"certainly buy {self.master} a nicer throne cushion. "
                        f"Meanwhile, {member.mention} has {recipient.dubloons} {self.dbl} to play with."
                    ),
                    (
                        f"Ah, the joy of taxation! Taking {dubloons} {self.dbl} from {member.mention} "
                        f"and adding it to our coffers. They've got {recipient.dubloons} {self.dbl} remaining."
                    ),
                    (
                        f"Congratulations, {member.mention}! You've won the 'Dubloonery Tax Lottery'. "
                        f"Prize? We're deducting {dubloons} {self.dbl} from your account. "
                        f"Don't worry, you still have {recipient.dubloons} {self.dbl} left to spend!"
                    )
                ]
                session.commit()
            else:
                replies = [
                    (
                        "Huh, looks like nobody who could afford a dubtax is on this discord. "
                        "Sorry, but nothing I can do boss."
                    )
                ]
        await ctx.send(random.choice(replies))

    @tax.error
    async def tax_error(self, ctx, error):
        GlobalVars.set_value("CAUGHT", 1)
        pe(error)
        logger.error(f"Author: {ctx.author} / Command: {ctx.message.content}. {error}")


def setup(bot):
    bot.add_cog(DBL(bot))
