import re
import random
import config as cfg
from logger import logger
from sqlalchemy import func, or_
from datetime import datetime
from db import SessionGame, sessionSupp, Users, Characters, Apps, BaseQuestions, Questions
from discord import Member, TextChannel
from discord.ext import commands
from exceptions import NoDiceFormatError, ConversionError
from valve import rcon
from google_api import sheets

async def get_application(applicant):
    return sessionSupp.query(Apps).filter_by(applicant=str(applicant)).first()

async def get_questions(application=None, applicant=None):
    if not application:
        application = await get_application(applicant)
    return application.questions if application else None

async def get_question(application=None, applicant=None, id=1, msg=''):
    if not application and not applicant:
        return None
    questions = await get_questions(application, applicant)
    txt = questions[id - 1].question
    num = len(questions)
    return f"{msg}\n__**Question {id} of {num}:**__\n> {parse(author, txt)}"

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
    sessionSupp.delete(application)
    sessionSupp.commit()

async def find_steamID64(application=None, applicant=None):
    if not application:
        application = await get_application(applicant)
    if not application:
        return None
    questions = await get_questions(application)
    if questions:
        questions[application.steamID_row - 1].answer
        result = re.search(r'(7\d{16})', questions[application.steamID_row - 1].answer)
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
    print(applicant, type(applicant))
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
        overview.append(buffer) # + msg)
    else:
        overview.append(buffer)
    return overview

async def whitelist_player(SteamID64, player):
    SteamID64 = str(SteamID64)
    if len(SteamID64) != 17 or not SteamID64.isnumeric():
        return "NotSteamIdError"
    elif SteamID64 == "76561197960287930":
        return "IsGabesIDError"
    try:
        msg = rcon.execute((cfg.RCON_IP, cfg.RCON_PORT), cfg.RCON_PASSWORD, f"WhitelistPlayer {SteamID64}")
    except:
        with open(cfg.WHITELIST_PATH, 'r') as f:
            lines = f.readlines()
            line = SteamID64 + "\n" if lines[-1][-1] == "\n" else "\n" + SteamID64 + "\n"
        with open(cfg.WHITELIST_PATH, 'a') as f:
            f.write(line)
        msg = f"Player {SteamID64} added to whitelist."
    success = True if msg == f"Player {SteamID64} added to whitelist." else False
    if success:
        # If either SteamID64 or disc_user already exist, delete them first
        sessionSupp.query(Users).filter(or_(Users.SteamID64==SteamID64, Users.disc_user==str(player))).delete()
        # Store SteamID64 <-> Discord Name link in db
        sessionSupp.add(Users(SteamID64=SteamID64, disc_user=str(player)))
        sessionSupp.commit()
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

async def roll_dice(dice):
    if dice.find('d') == -1:
        raise NoDiceFormatError()
    dice = dice.replace(" ","").split("+")
    val = 0
    lst = []
    for die in dice:
        if die.isnumeric():
            val += int(die)
        else:
            try:
                rolls, limit = map(int, die.split('d'))
            except Exception:
                raise NoDiceFormatError()
            lst += [random.randint(1, limit) for r in range(rolls)]
    result = "**" + "**, **".join([str(r) for r in lst]) + "**"
    result = rreplace(result, ",", " and", 1)
    result = result + " + **" + str(val) + "**" if val > 0 else result
    result = f"{result} (total: **{sum(lst) + val}**)" if len(lst) > 1 or val > 0 else result
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

def get_char(SteamID64):
    sessionGame = SessionGame()
    results = sessionGame.query(Characters.playerId, Characters.char_name, Characters.lastTimeOnline).filter(Characters.playerId.like(SteamID64 + '%')).order_by(Characters.playerId).all()
    sessionGame.close()
    lst = []
    for row in results:
        slot = str(row[0])[17] if len(str(row[0])) == 18 else 'active'
        lst.append({'name': str(row[1]), 'slot': slot, 'lastLogin': datetime.utcfromtimestamp(row[2]).strftime("%d-%b-%Y %H:%M:%S UTC")})
    return lst

def get_disc_user(SteamID64):
        result = sessionSupp.query(Users.disc_user).filter_by(SteamID64=SteamID64).first()
        return result[0] if result else None

def get_steamID64(arg):
    if type(arg) is Member:
        result = sessionSupp.query(Users.SteamID64).filter_by(disc_user=str(arg)).first()
        return result[0] if result else None
    else:
        sessionGame = SessionGame()
        result = sessionGame.query(Characters.playerId).filter(func.lower(Characters.char_name)==arg.lower()).first()
        sessionGame.close()
        if result:
            return result[0] if len(result[0]) == 17 else result[0][:-1]

def update_questions():
    cfg.GREETING = sheets.read(cfg.SPREADSHEET_ID, cfg.GREETING_RANGE)[0][0]
    cfg.APPLIED = sheets.read(cfg.SPREADSHEET_ID, cfg.APPLIED_RANGE)[0][0]
    cfg.FINISHED =sheets.read(cfg.SPREADSHEET_ID, cfg.FINISHED_RANGE)[0][0]
    cfg.COMMITED = sheets.read(cfg.SPREADSHEET_ID, cfg.COMMITED_RANGE)[0][0]
    cfg.ACCEPTED = sheets.read(cfg.SPREADSHEET_ID, cfg.ACCEPTED_RANGE)[0][0]
    cfg.REJECTED = sheets.read(cfg.SPREADSHEET_ID, cfg.REJECTED_RANGE)[0][0]
    cfg.REVIEWED = sheets.read(cfg.SPREADSHEET_ID, cfg.REVIEWED_RANGE)[0][0]
    cfg.WHITELISTING_FAILED = sheets.read(cfg.SPREADSHEET_ID, cfg.WHITELISTING_FAILED_RANGE)[0][0]
    cfg.WHITELISTING_SUCCEEDED = sheets.read(cfg.SPREADSHEET_ID, cfg.WHITELISTING_SUCCEEDED_RANGE)[0][0]
    cfg.APP_CLOSED = sheets.read(cfg.SPREADSHEET_ID, cfg.APP_CLOSED_RANGE)[0][0]

def create_application(applicant):
    new_app = Apps(applicant=str(applicant),
                   status='open',
                   steamID_row=None,
                   current_question=1,
                   open_date=datetime.utcnow())
    sessionSupp.add(new_app)
    for q in sessionSupp.query(BaseQuestions).all():
        if q.has_steamID:
            new_app.steamID_row=q.id
        sessionSupp.add(Questions(qnum=q.id, question=q.txt, answer='', application=new_app))
    sessionSupp.commit()
    return new_app

def parse(author, msg):
    msg = str(msg).replace('{PREFIX}', cfg.PREFIX) \
                  .replace('{OWNER}', cfg.GUILD.owner.mention) \
                  .replace('{PLAYER}', author.mention)
    for name, channel in cfg.CHANNEL.items():
        msg = re.sub("(?i){" + name + "}", channel.mention, msg)
    for name, role in cfg.ROLE.items():
        msg = re.sub("(?i){" + name + "}", role.mention, msg)
    return msg

def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)
