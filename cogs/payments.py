import asyncio
from discord.ext import commands
from discord.ext.commands import command
from logger import logger
from exiles_api import *
from functions import *
from config import *

class Payments(commands.Cog, name="Payment commands."):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def get_chars(user):
        chars = get_chars_by_user(user)
        char_ids, guild_ids, owners = [], [], {}
        for char in chars:
            char_ids.append(char.id)
            if char.has_guild:
                guild_ids.append(char.guild.id)
        for owner in session.query(CatUsers).order_by(CatUsers.id).all():
            if (owner.id in char_ids) or (owner.category.guild_pay and owner.id in guild_ids):
                if not owner.id in owners:
                    owners[owner.id] = [owner]
                else:
                    owners[owner.id].append(owner)
        return owners

    @staticmethod
    async def get_cat_names(cat_users):
        cats = [cat_user.category.cmd for cat_user in cat_users]
        return ', '.join(cats[:-1]) + ' and ' + cats[-1] if len(cats) > 1 else cats[0]

    @command(name='pm', help=f"Payment commands. Type {PREFIX}pm help for more information.")
    async def pm(self, ctx, *Arguments):
        guild = get_guild(self.bot)
        args = Arguments
        is_staff = has_support_role_or_greater(guild, ctx.author)

        # Command pm (1 arg)
        if len(args) == 0:
            owners = await Payments.get_chars(ctx.author)
            messages = []
            for owner_id, cat_users in owners.items():
                messages = await get_user_msg(cat_users, messages)
            await print_payments_msg(ctx.channel, messages)

        # Command pm add <category> <owner> (3+ args)
        elif args[0] == 'add' and len(args) < 3:
            if is_staff:
                await ctx.send("Command requires a category and a character or clan name.\n"
                              f"{PREFIX}pm add <category> <character or clan>")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
        elif args[0] == 'add':
            if is_staff:
                cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[1]).first()
                name = ' '. join(args[2:])
                cat_user = None
                if not cat:
                    await ctx.send(f"Couldn't find category **{args[1]}**. You may have to create one first.")
                else:
                    if cat.guild_pay:
                        owner = session.query(Guilds).filter(Guilds.name.collate('NOCASE') == name).first()
                        if not owner:
                            owner = session.query(Characters).filter(Characters.name.collate('NOCASE') == name).first()
                            if owner and owner.has_guild:
                                owner = owner.guild
                        if not owner:
                            await ctx.send(f"Couldn't find character or clan named **{name}**.")
                        else:
                            cat_user = CatUsers(id=owner.id, name=owner.name, category=cat)
                    else:
                        owner = session.query(Characters).filter(Characters.name.collate('NOCASE') == name).first()
                        if owner:
                            cat_user = CatUsers(id=owner.id, name=owner.name, category=cat)
                        else:
                            await ctx.send(f"Couldn't find character or clan named **{name}**.")
                if cat_user:
                    await ctx.send(f"Added **{owner.name}** to category **{cat.cmd}**. Their next due date has been "
                                   f"set to **{cat_user.next_due.strftime('%A %d-%b-%Y %H:%M UTC')}**")
                    session.add(cat_user)
                    session.commit()
                    payments_task = asyncio.create_task(payments(cat_user.id, cat_user.category_id))
                    payments_task.add_done_callback(exception_catching_callback)

            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")

        # Command pm remove <category> <owner> (3+ args)
        elif args[0] == 'remove' and len(args) < 2:
            if is_staff:
                await ctx.send("Command requires a category and a character or clan name. "
                               "If category is omitted character or clan will be removed from all categories.\n"
                              f"{PREFIX}pm remove [<category>] <character or clan>")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
        elif args[0] == 'remove':
            if is_staff:
                name_long = ' '.join(args[1:])
                name_short = ' '.join(args[2:])
                cat_users = session.query(CatUsers).filter(CatUsers.name.collate('NOCASE') == name_long).all()
                # no category name was given and user(s) exist => remove user from all categories
                if cat_users:
                    cat_nam = await self.get_cat_names(cat_users)
                    cat_nam = f"category **{cat_nam}**" if len(cat_users) == 1 else f"categories **{cat_nam}**"
                    await ctx.send(f"Removed **{cat_users[0].name}** from {cat_nam}.")
                    for cat_user in cat_users:
                        session.delete(cat_user)
                    session.commit()
                # category name was given or user name was spelled incorrectly
                else:
                    cat_name = args[1]
                    cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == cat_name).first()
                    # category name was given, user existence unclear
                    if cat:
                        filter = (CatUsers.name.collate('NOCASE') == name_short) & (CatUsers.category == cat)
                        cat_user = session.query(CatUsers).filter(filter).first()
                        # category name was given and user exists => remove user from that category
                        if cat_user:
                            await ctx.send(f"Removed **{cat_user.name}** from category **{cat.cmd}**.")
                            session.delete(cat_user)
                            session.commit()
                        # category name was given but user doesn't exists
                        else:
                            await ctx.send(f"Couldn't find **{name_short}** in category **{cat.cmd}**.\n"
                                           f"{PREFIX}pm remove [<category>] <character or clan>")
                    # category name and user were given but category doesn't exist or character name was misspelled
                    else:
                        await ctx.send(f"Couldn't find a user with the name **{name_long}** in any of the categories and "
                                       f"{cat_name} is not a valid category name.\n"
                                       f"{PREFIX}pm remove [<category>] <character or clan>")

        # Command pm give <amount> [<category>] <owner> (4+ args)
        elif args[0] in ('give', 'withdraw') and len(args) < 4:
            cmd = args[0].lower()
            if is_staff:
                await ctx.send("Command requires an amount, a category and a character or clan name. "
                              f"Category can be omitted if character or clan are only in one category.\n"
                              f"{PREFIX}pm {cmd} <amount> [<category>] <character or clan>")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
        elif args[0] in ('give', 'withdraw'):
            cmd = args[0].lower()
            if not is_staff:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
            else:
                amount = args[1]
                if not amount.isnumeric():
                    await ctx.send("Amount needs to be a positive numeric value.\n"
                                  f"{PREFIX}pm {cmd} <amount> [<category>] <character or clan>")
                # amount is guaranteed to be set to a positive number
                else:
                    cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[2]).first()
                    # category has either been omitted or misspelled
                    if not cat:
                        name_long = ' '.join(args[2:])
                        cat_users = session.query(CatUsers).filter(CatUsers.name.collate('NOCASE') == name_long).all()
                        # misspelled
                        if not cat_users:
                            await ctx.send(f"Couldn't find a user with the name **{name_long}** in any of the "
                                           f"categories and **{args[2]}** is not a valid category name.\n"
                                           f"{PREFIX}pm {cmd} <amount> [<category>] <character or clan>")
                        # ambiguous
                        elif len(cat_users) > 1:
                            cat_nam = self.get_cat_names(cat_users)
                            period = "period" if amout == '1' else "periods"
                            if cmd == 'give':
                                val = f"which of these categories should be given **{amount} billing {period}**"
                            else:
                                val = f"from which of these categories **{amount} billing {period}** should be withdrawn"
                            await ctx.send(f"**{cat_users[0].name}** is in categories **{cat_nam}**. "
                                           f"Please specify {val}.\n"
                                           f"{PREFIX}pm {cmd} <amount> [<category>] <character or clan>")
                        # category has been omitted and user is in only one category
                        else:
                            if cmd == 'give':
                                await ctx.send(f"**{cat_users[0].name}** has been given **{amount}** billing periods.")
                                cat_users[0].balance += int(amount)
                            else:
                                await ctx.send(f"**{amount}** billing periods have been "
                                               f"withdrawn from **{cat_users[0].name}**.")
                                cat_users[0].balance -= int(amount)
                            session.commit()
                    # category was given and found
                    else:
                        name_short = ' '.join(args[3:])
                        filter = (CatUsers.name.collate('NOCASE') == name_short) & (CatUsers.category == cat)
                        cat_user = session.query(CatUsers).filter(filter).first()
                        # no user with the given name was found in the given category
                        if not cat_user:
                            await ctx.send(f"Couldn't find a user with the name **{name_short}** in the "
                                           f"category **{cat.cmd}**. Did you misspell the name maybe?\n"
                                           f"{PREFIX}pm {cmd} <amount> [<category>] <character or clan>")
                        # user and category were found add amount to balance
                        else:
                            if cmd == 'give':
                                await ctx.send(f"**{cat_user.name}** has been given **{amount}** billing periods.")
                                cat_user.balance += int(amount)
                            else:
                                await ctx.send(f"**{amount}** billing periods have been "
                                               f"withdrawn from **{cat_user.name}**.")
                                cat_user.balance -= int(amount)
                            session.commit()

        # Command pm stats [<category>] [<owner>]
        elif args[0] == 'stats':
            if not is_staff:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
            # output a list of all categories and users
            elif len(args) == 1:
                cats = session.query(Categories).order_by(Categories.id).all()
                messages = []
                for cat in cats:
                    messages = await get_category_msg(cat, messages)
                await print_payments_msg(ctx.channel, messages)
            # output either list of all users within given category or all categories belonging to given user
            elif len(args) == 2:
                cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[1]).first()
                # output a list of all users within given category
                if cat:
                    messages = await get_category_msg(cat)
                    await print_payments_msg(ctx.channel, messages)
                # args[1] is user or misspelled
                else:
                    cat_users = session.query(CatUsers).filter(CatUsers.name.collate('NOCASE') == args[1]).all()
                    if not cat_users:
                        await ctx.send(f"Couldn't find **{args[1]}** in categories or users.\n"
                                       f"{PREFIX}pm stats [<category>] [<character or clan>]")
                    else:
                        messages = await get_user_msg(cat_users)
                        await print_payments_msg(ctx.channel, messages)
            # output either list of given user within given category or all categories belonging to given user
            elif len(args) > 2:
                cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[1]).first()
                # args[2] ... args[n] must be the users name
                if cat:
                    name = ' '.join(args[2:])
                    filter = (CatUsers.name.collate('NOCASE') == name) & (CatUsers.category == cat)
                    cat_user = session.query(CatUsers).filter(filter).first()
                    # no user with the given name was found in the given category
                    if not cat_user:
                        await ctx.send(f"Couldn't find a user with the name **{name}** in the "
                                       f"category **{cat.cmd}**. Did you misspell the name maybe?\n"
                                       f"{PREFIX}pm stats [<category>] [<character or clan>]")
                    # user and category were found
                    else:
                        messages = await get_user_msg([cat_user])
                        await print_payments_msg(ctx.channel, messages)
                # args[1] ... args[n] must be the users name
                else:
                    name = ' '.join(args[1:])
                    cat_users = session.query(CatUsers).filter(CatUsers.name.collate('NOCASE') == name).all()
                    # misspelled
                    if not cat_users:
                        await ctx.send(f"Couldn't find a user with the name **{name}** in any of the "
                                       f"categories and **{args[1]}** is not a valid category name.\n"
                                       f"{PREFIX}pm stats [<category>] [<character or clan>]")
                    else:
                        messages = await get_user_msg(cat_users)
                        await print_payments_msg(ctx.channel, messages)

        else:
            cmd = ' '.join(args)
            if is_staff:
                intro = f"Unknown command **{PREFIX}pm {cmd}**. " if args[0] != "help" else ""
                await ctx.send(f"{intro}Possible commands are:\n"
                               f"  {PREFIX}pm\n"
                               f"  {PREFIX}pm add <category> <character or clan>\n"
                               f"  {PREFIX}pm remove [<category>] <character or clan>\n"
                               f"  {PREFIX}pm give <amount> [<category>] <character or clan>\n"
                               f"  {PREFIX}pm withdraw <amount> [<category>] <character or clan>\n"
                               f"  {PREFIX}pm stats [<category>] [<character or clan>]")
            else:
                owners = await Payments.get_chars(ctx.author)
                messages = []
                for owner_id, cat_users in owners.items():
                    messages = await get_user_msg(cat_users, messages)
                await print_payments_msg(ctx.channel, messages)

        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

def setup(bot):
    bot.add_cog(Payments(bot))
