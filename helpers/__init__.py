import re
import random
import config as cfg
from sqlalchemy import func, or_
from datetime import datetime
from db import SessionGame, sessionUser, User, Characters
from discord import Member
from exceptions import NoDiceFormatError
from valve import rcon
from google_api import sheets

async def send_question(author, id, msg=''):
    await author.dm_channel.send(f"{msg}\n__**Question {id + 1} of {len(cfg.QUESTIONS)}:**__\n> {parse(author, cfg.QUESTIONS[id])}")

async def send_overview(author, msg='', submitted=False):
    channel = cfg.CHANNEL[cfg.APPLICATIONS] if submitted else author.dm_channel
    if len(cfg.APL[author]['answers']) == 0:
        await channel.send("No questions answered yet!" + msg)
        return
    buffer = ''
    for id in range(len(cfg.QUESTIONS)):
        if id in cfg.APL[author]['answers']:
            if len(buffer) + 21 + len(parse(author, cfg.QUESTIONS[id])) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += f"__**Question {id + 1}:**__\n> {parse(author, cfg.QUESTIONS[id])}\n"
            if len(buffer) + len(cfg.APL[author]['answers'][id]) > 2000:
                await channel.send(buffer)
                buffer = ''
            buffer += cfg.APL[author]['answers'][id] + "\n"
    if msg and len(buffer) + len(msg) > 2000:
        await channel.send(buffer)
        await channel.send(msg)
    elif msg:
        await channel.send(buffer + msg)
    else:
        await channel.send(buffer)

async def write_to_whitelist(SteamID64):
        with open(cfg.WHITELIST_PATH, 'r') as f:
            lines = f.readlines()
            line = SteamID64 + "\n" if lines[-1][-1] == "\n" else "\n" + SteamID64 + "\n"
        with open(cfg.WHITELIST_PATH, 'a') as f:
            f.write(line)

async def whitelist_player(ctx, SteamID64, player):
    SteamID64 = str(SteamID64)
    if len(SteamID64) != 17 or not SteamID64.isnumeric():
        return "NotSteamIdError"
    elif SteamID64 == "76561197960287930":
        return "IsGabesIDError"
    try:
        msg = rcon.execute((cfg.RCON_IP, cfg.RCON_PORT), cfg.RCON_PASSWORD, f"WhitelistPlayer {SteamID64}")
    except:
        await write_to_whitelist(SteamID64)
        msg = f"Player {SteamID64} added to whitelist."
    if msg == "Still processing previous command.":
        await write_to_whitelist(SteamID64)
        msg = f"Player {SteamID64} added to whitelist."
    success = True if msg == f"Player {SteamID64} added to whitelist." else False
    if success:
        # If either SteamID64 or disc_user already exist, delete them first
        sessionUser.query(User).filter(or_(User.SteamID64==SteamID64, User.disc_user==str(player))).delete()
        # Store SteamID64 <-> Discord Name link in db
        sessionUser.add(User(SteamID64=SteamID64, disc_user=str(player)))
        sessionUser.commit()
        return msg
    elif msg.find("Invalid argument") >= 0:
        return f"FailedError|{msg}"
    else:
        return msg

async def find_last_Applicant(ctx, user):
    async for message in ctx.channel.history(limit=100):
        if message.author == user:
            pos_end = message.content.find(" has filled out the application. You can now either")
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

def find_steamID64(author):
    result = re.search(r'(7\d{16})', cfg.APL[author]['answers'][cfg.STEAMID_QUESTION])
    result = result.group(1) if result else None
    return result

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
        result = sessionUser.query(User.disc_user).filter_by(SteamID64=SteamID64).first()
        return result[0] if result else None

def get_steamID64(arg):
    if type(arg) is Member:
        result = sessionUser.query(User.SteamID64).filter_by(disc_user=str(arg)).first()
        return result[0] if result else None
    else:
        sessionGame = SessionGame()
        result = sessionGame.query(Characters.playerId).filter(func.lower(Characters.char_name)==arg.lower()).first()
        sessionGame.close()
        if result:
            return result[0] if len(result[0]) == 17 else result[0][:-1]

def update_questions():
    cfg.QUESTIONS = [value[0] for value in sheets.read(cfg.SPREADSHEET_ID, cfg.QUESTIONS_RANGE)]
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

def find_next_unanswered(author):
    if len(cfg.APL[author]['answers']) >= len(cfg.QUESTIONS):
        return -1
    for id in range(len(cfg.QUESTIONS)):
        if id not in cfg.APL[author]['answers']:
            return id
    return -1

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
