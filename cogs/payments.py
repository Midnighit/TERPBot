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
    async def get_groups(user):
        chars = get_chars_by_user(user)
        char_ids, guild_ids, groups = [], [], {}
        for char in chars:
            char_ids.append(char.id)
            if char.has_guild:
                guild_ids.append(char.guild.id)
        for owner in session.query(CatOwners).order_by(CatOwners.id).all():
            if (owner.id in char_ids) or (owner.category.guild_pay and owner.id in guild_ids):
                if not owner.group.id in groups:
                    groups[owner.group.id] = [owner.group]
                else:
                    groups[owner.group.id].append(owner.group)
        return groups

    @staticmethod
    async def get_cat_names(groups=None, cat_owners=None):
        if groups or cat_owners:
            if groups:
                cats = [group.category.cmd for group in groups]
            if cat_owners:
                cats = [cat_owner.group.category.cmd for cat_owner in cat_owners]
            return '**, **'.join(cats[:-1]) + '** and **' + cats[-1] if len(cats) > 1 else cats[0]
        return None

    @command(name='pm', help=f"Payment commands. Type {PREFIX}pm help for more information.")
    async def pm(self, ctx, *Arguments):
        guild = get_guild(self.bot)
        args = Arguments
        is_staff = has_support_role_or_greater(guild, ctx.author)
        # print(f"len(args): {len(args)}")
        # for idx in range(len(args)):
        #     print(f"{idx}: {args[idx]}")

        # Command pm (1 arg)
        if len(args) == 0:
            group_list = await Payments.get_groups(ctx.author)
            if len(group_list) == 0:
                await ctx.send("You have no characters or clans on any of the payment lists.")
            else:
                messages = []
                for owner_id, groups in group_list.items():
                    messages = await get_user_msg(groups, messages)
                await print_payments_msg(ctx.channel, messages)

        # Command pm group add|show <group name> [<category>] [<owner>]
        elif args[0] == 'group' and \
             ((len(args) < 2) or \
             (args[1] in ('add', 'delete') and len(args) < 4) or \
             (not args[1] in ('add', 'delete', 'show'))):
            if is_staff:
                await ctx.send("Command requires the keyword add, remove or show and a group name. "
                               "If keyword wasn't show it also requires a character or clan name. "
                               "A category is only required if character or clan are in multiple categories\n"
                              f"{PREFIX}pm group add|delete|show <group> [<category>] [<character, clan or group>]")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
        elif args[0] == 'group' and args[1] == 'add':
            grp = session.query(Groups).filter(Groups._name.collate('NOCASE') == args[2]).first()
            cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[3]).first()
            if not grp and not cat:
                await ctx.send(f"Command requires either an existing group name or a new group name and category.\n"
                         f"{PREFIX}pm group add <group> [<category>] [<character, clan or group>]")
            elif grp and cat and grp.category != cat:
                await ctx.send(f"Group **{grp.name}** already exists and is assigned to category **{grp.category.cmd}**. "
                         f"If group needs to be reassigned to category **{cat.cmd}** you'll have to remove and "
                          "recreate it under the new category again.\n"
                         f"{PREFIX}pm group add <group> [<category>] [<character, clan or group>]")
            else:
                # if group doesn't exist but category is found, create new group
                if not grp and cat:
                    existed = False
                    grp = Groups(name=args[2], category=cat)
                    name = ' '. join(args[4:])
                    next_due = None
                # if group exists but category isn't found, determine group
                elif grp and not cat:
                    existed = True
                    cat = grp.category
                    name = ' '. join(args[3:])
                    next_due=grp.next_due
                if cat.guild_pay:
                    owners = Owner.get_by_name(name, nocase=True)
                    if len(owners) == 0:
                        await ctx.send(f"Couldn't find character or clan named **{name}**.")
                    elif len(owners) > 1:
                        await ctx.send("Name ambiguous. "
                                      f"At least two characters or clans with name **{name}** were found.")
                    else:
                        owner = owners[0]
                        if not owner.is_guild and owner.has_guild:
                            owner = owner.guild
                        cat_owner = CatOwners(id=owner.id, next_due=next_due, category=cat, group=grp)
                else:
                    owners = Owner.get_by_name(name, nocase=True, include_guilds=False)
                    if len(owners) == 0:
                        await ctx.send(f"Couldn't find character named **{name}**.")
                    elif len(owners) > 1:
                        await ctx.send("Name ambiguous. "
                                      f"At least two characters with name **{name}** were found.")
                    else:
                        owner = owners[0]
                        cat_owner = CatOwners(id=owner.id, next_due=next_due, category=cat, group=grp)
                if cat_owner:
                    tense = 'is' if existed else 'has been set to'
                    session.add(cat_owner)
                    session.commit()
                    await ctx.send(f"Added **{owner.name}** to group **{grp.name}** belonging to "
                                   f"category **{cat.cmd}**. Their next due date {tense} "
                                   f"**{cat_owner.next_due.strftime('%A %d-%b-%Y %H:%M UTC')}**")
                    if not existed:
                        payments_task = asyncio.create_task(payments(cat_owner.group.id, cat_owner.category.id))
                        payments_task.add_done_callback(exception_catching_callback)
        elif args[0] == 'group' and args[1] == 'delete':
            if len(args) < 3:
                await ctx.send(f"Command requires a group name to be deleted.\n"
                               f"{PREFIX}pm group delete <group>")
            else:
                name = ' '.join(args[2:])
                group = session.query(Groups).filter(Groups._name.collate('NOCASE') == name).first()
                if not group:
                    await ctx.send(f"No group with the name **{name}** has been found.\n"
                                   f"{PREFIX}pm group delete <group>")
                else:
                    name = group.name
                    for cat_owner in group.owners:
                        session.delete(cat_owner)
                    session.delete(group)
                    session.commit()
                    await ctx.send(f"Group **{name}** and all of its members have been deleted.")
        elif args[0] == 'group' and args[1] == 'show':
            # show all groups
            if len(args) == 2:
                groups = [group for group in session.query(Groups).filter(Groups._name != None).all()]
                message = await get_user_msg(groups)
                await print_payments_msg(ctx.channel, message)
            else:
                name = ' '.join(args[2:])
                group = session.query(Groups).filter(Groups._name.collate('NOCASE') == name).first()
                if not group:
                    await ctx.send(f"No group with the name **{name}** has been found.")
                else:
                    if len(group.owners) == 0:
                        await ctx.send(f"Group **{group.name}** currently has no members.")
                    else:
                        messages = await get_user_msg([group])
                        message = messages[0] + f"It currently has the following members:\n"
                        for owner in group.owners:
                            message += f"**{owner.name}**\n"
                        await ctx.send(message)

        # Command pm add <category> <owner> (3+ args)
        elif args[0] == 'add' and len(args) < 3:
            if is_staff:
                await ctx.send("Command requires a category and a character or clan name.\n"
                              f"{PREFIX}pm add <category> <character, clan or group>")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
        elif args[0] == 'add':
            if is_staff:
                cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[1]).first()
                name = ' '. join(args[2:])
                cat_owner = None
                if not cat:
                    await ctx.send(f"Couldn't find category **{args[1]}**. You may have to create one first.")
                else:
                    if cat.guild_pay:
                        owners = Owner.get_by_name(name, nocase=True)
                        if len(owners) == 0:
                            await ctx.send(f"Couldn't find character or clan named **{name}**.")
                        elif len(owners) > 1:
                            await ctx.send("Name ambiguous. "
                                          f"At least two characters or clans with name **{name}** were found.")
                        else:
                            owner = owners[0]
                            if not owner.is_guild and owner.has_guild:
                                owner = owner.guild
                            filter = (CatOwners.id==owner.id) & (CatOwners.group_id==Groups.id)
                            exist = session.query(CatOwners.id, Groups.category_id).filter(filter).all()
                            if (owner.id, cat.id) in exist:
                                await ctx.send(f"**{owner.name}** is already assigned to category **{cat.cmd}**.")
                            else:
                                cat_owner = CatOwners(id=owner.id, category=cat)
                    else:
                        owners = Owner.get_by_name(name, nocase=True, include_guilds=False)
                        if len(owners) == 0:
                            await ctx.send(f"Couldn't find character named **{name}**.")
                        elif len(owners) > 1:
                            await ctx.send("Name ambiguous. "
                                          f"At least two characters with name **{name}** were found.")
                        else:
                            owner = owners[0]
                            filter = (CatOwners.id==owner.id) & (CatOwners.group_id==Groups.id)
                            exist = session.query(CatOwners.id, Groups.category_id).filter(filter).all()
                            if (owner.id, cat.id) in exist:
                                await ctx.send(f"**{owner.name}** is already assigned to category **{cat.cmd}**.")
                            else:
                                cat_owner = CatOwners(id=owner.id, category=cat)
                if cat_owner:
                    session.add(cat_owner)
                    session.commit()
                    payments_task = asyncio.create_task(payments(cat_owner.group.id, cat_owner.category.id))
                    payments_task.add_done_callback(exception_catching_callback)
                    await ctx.send(f"Added **{owner.name}** to category **{cat.cmd}**. Their next due date has been "
                                   f"set to **{cat_owner.next_due.strftime('%A %d-%b-%Y %H:%M UTC')}**")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")

        # Command pm remove [<category>] <owner> (2+ args)
        elif args[0] == 'remove' and len(args) < 2:
            if is_staff:
                await ctx.send("Command requires a category and a character or clan name. "
                               "If category is omitted character or clan will be removed from all categories.\n"
                              f"{PREFIX}pm remove [<category>] <character, clan or group>")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
        elif args[0] == 'remove':
            if is_staff:
                name_long = ' '.join(args[1:])
                name_short = ' '.join(args[2:])
                owners = Owner.get_by_name(name_long, nocase=True)
                owner_ids = [o.id for o in owners]
                cat_owners = session.query(CatOwners).filter(CatOwners.id.in_(owner_ids)).all()
                # no category name was given and user(s) exist => remove user from all categories
                if cat_owners:
                    cat_nam = await self.get_cat_names(cat_owners=cat_owners)
                    cat_nam = f"category **{cat_nam}**" if len(cat_owners) == 1 else f"categories **{cat_nam}**"
                    name = cat_owners[0].name
                    for cat_owner in cat_owners:
                        if cat_owner.is_simple_group:
                            session.delete(cat_owner.group)
                        session.delete(cat_owner)
                    session.commit()
                    await ctx.send(f"Removed **{name}** from {cat_nam}.")
                # category name was given or user name was spelled incorrectly
                else:
                    cat_name = args[1]
                    cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == cat_name).first()
                    # category name was given, user existence unclear
                    if cat:
                        owner_ids = [o.id for o in Owner.get_by_name(name_short, nocase=True)]
                        filter = ((CatOwners.group_id == Groups.id) &
                                  (Groups.category_id == cat.id) &
                                  (Groups._name.collate('NOCASE') == name_short) |
                                  (CatOwners.id.in_(owner_ids)))
                        cat_owner = session.query(CatOwners).filter(filter).first()
                        # category name was given and user exists => remove user from that category
                        if cat_owner:
                            name = cat_owner.name
                            if cat_owner.is_simple_group:
                                session.delete(cat_owner.group)
                            session.delete(cat_owner)
                            session.commit()
                            await ctx.send(f"Removed **{name}** from category **{cat.cmd}**.")
                        # category name was given but user doesn't exists
                        else:
                            await ctx.send(f"Couldn't find **{name_short}** in category **{cat.cmd}**."
                                           f"{PREFIX}pm remove [<category>] <character, clan or group>")
                    # category name and user were given but category doesn't exist or character name was misspelled
                    else:
                        await ctx.send(f"Couldn't find a user with the name **{name_long}** in any of the categories and "
                                       f"{cat_name} is not a valid category name.\n"
                                       f"{PREFIX}pm remove [<category>] <character, clan or group>")

        # Command pm give|withdraw <amount> [<category>] <owner> (3+ args)
        elif args[0].lower() in ('give', 'withdraw') and len(args) < 3:
            cmd = args[0].lower()
            if is_staff:
                await ctx.send("Command requires an amount, a category and a character or clan name. "
                              f"Category can be omitted if character or clan are only in one category.\n"
                              f"{PREFIX}pm {cmd} <amount> [<category>] <character, clan or group>")
            else:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
        elif args[0].lower() in ('give', 'withdraw'):
            cmd = args[0].lower()
            if not is_staff:
                await ctx.send("Command may only be used by users with role greater or equal than Support Staff.")
            else:
                amount = args[1]
                if not amount.isnumeric():
                    await ctx.send("Amount needs to be a positive numeric value.\n"
                                  f"{PREFIX}pm {cmd} <amount> [<category>] <character, clan or group>")
                # amount is guaranteed to be set to a positive number
                else:
                    cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[2]).first()
                    # category has either been omitted or misspelled
                    if not cat:
                        name_long = ' '.join(args[2:])
                        # owner_ids = [o.id for o in Owner.get_by_name(name_long, nocase=True)]
                        owner_ids = []
                        for o in Owner.get_by_name(name_long, nocase=True):
                            owner_ids.append(o.id)
                            if o.is_character and o.has_guild:
                                owner_ids.append(o.guild.id)
                        filter = ((CatOwners.group_id == Groups.id) &
                                  ((Groups._name.collate('NOCASE') == name_long) | (CatOwners.id.in_(owner_ids))))
                        groups = session.query(Groups).filter(filter).all()

                        # misspelled
                        if not groups:
                            await ctx.send(f"Couldn't find a character, clan or group with the name **{name_long}** "
                                           f"in any of the categories and **{args[2]}** is not a valid category name.\n"
                                           f"{PREFIX}pm {cmd} <amount> [<category>] <character, clan or group>")
                        # ambiguous
                        elif len(groups) > 1:
                            name = name_long
                            for group in groups:
                                if group.name.lower() == name_long.lower():
                                    name = group.name
                                    break
                            cat_nam = await self.get_cat_names(groups=groups)
                            period = "period" if amount == '1' else "periods"
                            if cmd == 'give':
                                val = f"which of these categories should be given **{amount}** billing {period}"
                            else:
                                val = (f"from which of these categories **{amount}** billing {period} "
                                        "should be withdrawn")
                            await ctx.send(f"**{name}** is in categories **{cat_nam}**. "
                                           f"Please specify {val}.\n"
                                           f"{PREFIX}pm {cmd} <amount> [<category>] <character, clan or group>")
                        # category has been omitted and user is in only one category
                        else:
                            period = "period" if amount == '1' else "periods"
                            if cmd == 'give':
                                groups[0].balance += int(amount)
                                session.commit()
                                await ctx.send(f"**{groups[0].name}** has been given **{amount}** "
                                               f"billing {period} in category **{groups[0].category.cmd}**.")
                            else:
                                groups[0].balance -= int(amount)
                                session.commit()
                                has = 'has' if amount == 1 else 'have'
                                await ctx.send(f"**{amount}** billing {period} {has} been withdrawn "
                                               f"from **{groups[0].name}** in category **{groups[0].category.cmd}**.")
                    # category was given and found
                    else:
                        name_short = ' '.join(args[3:])
                        owners = Owner.get_by_name(name_short, nocase=True)
                        owner_ids = [o.guild.id if o.is_character and o.has_guild else o.id for o in owners]
                        filter = ((CatOwners.group_id == Groups.id) &
                                  (Groups.category_id == cat.id) &
                                  ((Groups._name.collate('NOCASE') == name_short) | (CatOwners.id.in_(owner_ids))))
                        group = session.query(Groups).filter(filter).first()
                        # no user with the given name was found in the given category
                        if not group:
                            await ctx.send(f"Couldn't find a user with the name **{name_short}** in the "
                                           f"category **{cat.cmd}**. Did you misspell the name maybe?\n"
                                           f"{PREFIX}pm {cmd} <amount> [<category>] <character, clan or group>")
                        # user and category were found add amount to balance
                        else:
                            period = 'period' if amount == 1 else 'periods'
                            if cmd == 'give':
                                group.balance += int(amount)
                                session.commit()
                                await ctx.send(f"**{group.name}** has been given **{amount}** billing {period} "
                                               f"in category **{cat.cmd}**")
                            else:
                                group.balance -= int(amount)
                                session.commit()
                                has = 'has' if amount == 1 else 'have'
                                await ctx.send(f"**{amount}** billing {period} {has} been "
                                               f"withdrawn from **{group.name}** in category **{cat.cmd}**.")

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
                    owner_ids = [o.id for o in Owner.get_by_name(args[1], nocase=True)]
                    filter = ((CatOwners.group_id == Groups.id) &
                              (Groups._name.collate('NOCASE') == args[1]) |
                              (CatOwners.id.in_(owner_ids)))
                    groups = session.query(Groups).filter(filter).all()
                    if not groups:
                        await ctx.send(f"Couldn't find **{args[1]}** in categories or users.\n"
                                       f"{PREFIX}pm stats [<category>] [<character, clan or group>]")
                    else:
                        messages = await get_user_msg(groups)
                        await print_payments_msg(ctx.channel, messages)
            # output either list of given user within given category or all categories belonging to given user
            elif len(args) > 2:
                cat = session.query(Categories).filter(Categories.cmd.collate('NOCASE') == args[1]).first()
                # args[2] ... args[n] must be the users name
                if cat:
                    name = ' '.join(args[2:])
                    owner_ids = [o.id for o in Owner.get_by_name(name, nocase=True)]
                    filter = ((CatOwners.group_id == Groups.id) &
                              (Groups.category_id == cat.id) &
                              (Groups._name.collate('NOCASE') == name) |
                              (CatOwners.id.in_(owner_ids)))
                    group = session.query(Groups).filter(filter).first()
                    # no user with the given name was found in the given category
                    if not group:
                        await ctx.send(f"Couldn't find a user with the name **{name}** in the "
                                       f"category **{cat.cmd}**. Did you misspell the name maybe?\n"
                                       f"{PREFIX}pm stats [<category>] [<character, clan or group>]")
                    # user and category were found
                    else:
                        messages = await get_user_msg([group])
                        await print_payments_msg(ctx.channel, messages)
                # args[1] ... args[n] must be the users name
                else:
                    name = ' '.join(args[1:])
                    owner_ids = [o.id for o in Owner.get_by_name(name, nocase=True)]
                    filter = ((CatOwners.group_id == Groups.id) &
                              (Groups._name.collate('NOCASE') == name) |
                              (CatOwners.id.in_(owner_ids)))
                    groups = session.query(Groups).filter(filter).all()
                    # misspelled
                    if not groups:
                        await ctx.send(f"Couldn't find a user with the name **{name}** in any of the "
                                       f"categories and **{args[1]}** is not a valid category name.\n"
                                       f"{PREFIX}pm stats [<category>] [<character, clan or group>]")
                    else:
                        messages = await get_user_msg(groups)
                        await print_payments_msg(ctx.channel, messages)

        else:
            cmd = ' '.join(args)
            if is_staff:
                intro = f"Unknown command **{PREFIX}pm {cmd}**. " if args[0] != "help" else ""
                await ctx.send(f"{intro}Possible commands are:\n"
                               f"  {PREFIX}pm\n"
                               f"  {PREFIX}pm group show [<group>]\n"
                               f"  {PREFIX}pm group add|delete <group> [<category>] [<character, clan or group>]\n"
                               f"  {PREFIX}pm add|remove [<category>] <character, clan or group>\n"
                               f"  {PREFIX}pm give|withdraw <amount> [<category>] <character, clan or group>\n"
                               f"  {PREFIX}pm stats [<category>] [<character, clan or group>]")
            else:
                group_list = await Payments.get_groups(ctx.author)
                messages = []
                for owner_id, groups in group_list.items():
                    messages = await get_user_msg(groups, messages)
                await print_payments_msg(ctx.channel, messages)

        logger.info(f"Author: {ctx.author} / Command: {ctx.message.content}.")

def setup(bot):
    bot.add_cog(Payments(bot))
