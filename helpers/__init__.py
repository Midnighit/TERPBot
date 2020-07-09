import re
import random
import config as saved
from config import *
from logger import logger
from sqlalchemy import func, or_
from datetime import datetime
from exiles_api import session, Users, Characters, Applications, BaseQuestions, Questions
from discord import Member, TextChannel
from discord.ext import commands
from exceptions import NoDiceFormatError, ConversionError
from valve import rcon

async def get_application(applicant):
    return session.query(Applications).filter_by(applicant=str(applicant)).first()

async def get_questions(application=None, applicant=None):
    if not application:
        application = await get_application(applicant)
    return application.questions if application else None

async def get_question(application, applicant, id=1, msg=''):
    if not application or not applicant:
        return None
    questions = await get_questions(application, applicant)
    txt = questions[id - 1].question
    num = len(questions)
    return f"{msg}\n__**Question {id} of {num}:**__\n> {parse(applicant, txt)}"

async def get_next_unanswered(application=None, applicant=None):
    questions = await get_questions(application, applicant)
    if questions:
        for q in questions:
            if q.answer == '':
                return q.qnum
    return -1

async def get_num_questions(application=None, applicant=None):
    questions = await get_questions(application, applicant)
    return len(questions) if questions else 0

async def can_edit_questions(application=None, applicant=None):
    if not application:
        application = await get_application(applicant)
    if not application:
        return False
    status = application.status
    return application.status in ('open', 'finished', 'review')

async def delete_application(application=None, applicant=None):
    if not application:
        application = await get_application(applicant)
    if not application:
        return None
    session.delete(application)
    session.commit()

async def find_steam_id_in_answer(application=None, applicant=None):
    if not application:
        application = await get_application(applicant)
    if not application:
        return None
    questions = await get_questions(application)
    if questions:
        questions[application.steam_id_row - 1].answer
        result = re.search(r'(7\d{16})', questions[application.steam_id_row - 1].answer)
        result = result.group(1) if result else None
        return result

async def get_overview(application, applicant, msg=''):
    if not application:
        application = await get_application(applicant)
    if not application:
        return None
    give_overview = False
    questions = await get_questions(application, applicant)
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
            if len(buffer) + 21 + len(parse(applicant, questions[id].question)) > 2000:
                overview.append(buffer)
                buffer = ''
            buffer += f"__**Question {id + 1}:**__\n> {parse(applicant, questions[id].question)}\n"
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

async def write_to_whitelist(SteamID64):
        with open(WHITELIST_PATH, 'r') as f:
            lines = f.readlines()
            line = SteamID64 + "\n" if lines[-1][-1] == "\n" else "\n" + SteamID64 + "\n"
        with open(WHITELIST_PATH, 'a') as f:
            f.write(line)

async def whitelist_player(ctx, SteamID64, player):
    steam_id = str(SteamID64)
    if len(steam_id) != 17 or not steam_id.isnumeric():
        return "NotSteamIdError"
    elif steam_id == "76561197960287930":
        return "IsGabesIDError"
    # determine discord user to be whitelisted
    try:
        member = await commands.MemberConverter().convert(ctx, player)
    except:
        raise ConversionError
    # check if discord user is already in db
    user = session.query(Users).filter_by(disc_id=member.id).first()
    if not user:
        user = session.query.(Users).filter_by(disc_user=disc_user).first()
        if user:
            user.disc_id = member.id
            session.commit()
    # if user is not in db, create a new one
    if not user:
        user = Users(steam_id=steam_id, disc_user=str(member), disc_id=member.id)
        session.add(user)
        session.commit()
    # try to link user to funcom_id/player_id
    # Question: How do I get a funcom_id for a player who hasn't logged into create a character because they're not whitelisted
    # result = session.query(Steam64.funcom_id).filter_by(id=steam_id).first()
    # if not result:
    #     await ctx.send(f"No FuncomID associated with SteamID64 {steam_id} has been found. Did you already claim.")
    try:
        msg = rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, f"WhitelistPlayer {user.funcom_id}")
    except:
        await write_to_whitelist(steam_id)
        msg = f"Player {steam_id} added to whitelist."
    if msg == "Still processing previous command.":
        await write_to_whitelist(steam_id)
        msg = f"Player {steam_id} added to whitelist."
    success = True if msg == f"Player {steam_id} added to whitelist." else False
    if success:
        users = session.query(Users).filter((Users.steam_id==steam_id) | (Users.disc_user==str(player))).all()
        if len(users) > 1:
            await ctx.send(f"SteamID64 {steam_id} has already been registered by another user. Please make sure this is really yours. If you are sure, please contact an admin for clarification.")
            return
        elif len(users) == 1:
            users[0].steam_id = steam_id
        else:
            session.add(Users(steam_id=steam_id, disc_user=str(player)))
        session.commit()
        return msg
    elif msg.find("Invalid argument") >= 0:
        return f"FailedError|{msg}"
    else:
        return msg

async def find_last_applicant(ctx, user):
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

class Die:
    def __init__(self, num=1, sides=1, sign=1):
        self.num = num
        self.sides = sides
        self.sign = sign

    def __repr__(self):
        return f"<Die(num={self.num}, sides={self.sides}, sign={self.sign})>"

    @property
    def sign(self):
        return self._sign

    @sign.setter
    def sign(self, value):
        if type(value) is str:
            if value == "+":
                self._sign = 1
            elif value == "-":
                self._sign = -1
        elif type(value) is int:
            if value >= 0:
                self._sign = 1
            else:
                self._sign = -1

    @property
    def num(self):
        return self._num

    @num.setter
    def num(self, value):
        if type(value) is int:
            if value > 0:
                self._num = value

    @property
    def sides(self):
        return self._sides

    @sides.setter
    def sides(self, value):
        if type(value) is int:
            if value > 0:
                self._sides = value

    def roll(self):
        sum = 0
        for i in range(self._num):
            sum += random.randint(1, self._sides)
        return sum * self._sign

class Dice(list):
    def roll(self):
        sum = 0
        results = []
        for d in self:
            r = d.roll()
            results.append(r)
            sum += r
        return (results, sum)

    def __repr__(self):
        repr = "<Dice("
        idx = 0
        for d in self:
            repr += f"die{idx}={'-' if d.sign < 0 else ''}{d.num}d{d.sides}, "
            idx += 1
        return repr[:-2] + ")>"

async def roll_dice(input):
    if input.find('d') == -1:
        raise NoDiceFormatError()
    input = input.replace(" ","")
    dice = Dice()
    num = ''
    type = 's'
    sign = '+'
    val = 0
    for c in input:
        if c in ('+', '-'):
            if type == 's' and num != '':
                val = val - int(num) if sign == '-' else val + int(num)
            elif type == 's' and num == '':
                pass
            elif num != '':
                d.sides = int(num)
                d.sign = sign
                dice.append(d)
            else:
                raise NoDiceFormatError()
            num = ''
            type = 's'
            sign = c
        elif c == 'd':
            d = Die(num=int(num)) if num != '' else Die()
            num = ''
            type = 'd'
        else:
            if not c.isnumeric():
                raise NoDiceFormatError()
            num += c
    if type == 's' and num != '':
        val = val - int(num) if sign == '-' else val + int(num)
    elif num != '':
        d.sides = int(num)
        d.sign = sign
        dice.append(d)
    else:
        raise NoDiceFormatError()

    lst, sum = dice.roll()

    result = "**" + "**, **".join([str(r) for r in lst]) + "**"
    result = rreplace(result, ",", " and", 1)
    if val > 0:
        result = result + " + **" + str(val) + "**"
    elif val < 0:
        result = result + " - **" + str(abs(val)) + "**"
    result = f"{result} (total: **{str(sum + val)}**)" if len(lst) > 1 or val != 0 else result
    return result

async def convert_user(ctx, user):
    if user is None:
        raise ConversionError("Missing argument user.")
    try:
        user = await commands.MemberConverter().convert(ctx, user)
        return (user, user.mention)
    except:
        try:
            user = await commands.MemberConverter().convert(ctx, user.capitalize())
            return (user, user.mention)
        except:
            pass
    user = str(user)
    if len(user) > 5 and user[-5] == '#':
        return (user, user)
    raise ConversionError(f"Couldn't determine discord account of {user}")

async def is_time_format(time):
    tLst = time.split(':')
    if not tLst:
        return False

    if len(tLst) >= 1 and tLst[0].isnumeric() and int(tLst[0]) >= 0:
        hours = str(int(tLst[0]) % 24)
    else:
        return False

    if len(tLst) >= 2 and tLst[1].isnumeric() and int(tLst[1]) >= 0 and int(tLst[1]) < 60:
        minutes = tLst[1]
    elif len(tLst) < 2:
        minutes = '00'
    else:
        return False

    if len(tLst) >= 3 and tLst[2].isnumeric() and int(tLst[2]) >= 0 and int(tLst[2]) < 60:
        seconds = tLst[2]
    elif len(tLst) < 3:
        seconds = '00'
    else:
        return False

    return ':'.join([hours, minutes, seconds])

def set_time_decimal():
    logger.info(f"Trying to reset the time to the previously read time of {LAST_RESTART_TIME}")
    try:
        rcon.execute((RCON_IP, RCON_PORT), RCON_PASSWORD, f"TERPO setTimeDecimal {LAST_RESTART_TIME}")
        logger.info("Time was reset successfully!")
    except Exception as error:
        raise RConConnectionError(error.args[1])
    saved.LAST_RESTART_TIME = 12.0

def create_application(applicant):
    new_app = Applications(applicant=str(applicant),
                           status='open',
                           steam_id_row=None,
                           current_question=1,
                           open_date=datetime.utcnow())
    session.add(new_app)
    for q in session.query(BaseQuestions).all():
        if q.has_steam_id:
            new_app.steam_id_row=q.id
        session.add(Questions(qnum=q.id, question=q.txt, answer='', application=new_app))
    session.commit()
    return new_app

def parse(user, msg):
    msg = str(msg).replace('{PREFIX}', PREFIX) \
                  .replace('{OWNER}', saved.GUILD.owner.mention)
    msg = msg.replace('{PLAYER}', user.mention) if type(user) == Member else msg.replace('{PLAYER}', str(user))
    for name, channel in saved.CHANNEL.items():
        msg = re.sub("(?i){" + name + "}", channel.mention, msg)
    for name, role in saved.ROLE.items():
        msg = re.sub("(?i){" + name + "}", role.mention, msg)
    return msg

def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)
