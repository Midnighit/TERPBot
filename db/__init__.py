from sqlalchemy import create_engine, Column, ForeignKey, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.ext.declarative import declarative_base
import config as cfg

# setup the metadata
Base = declarative_base()

class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    SteamID64 = Column(String(17), unique=True, nullable=False)
    disc_user = Column(String, unique=True, nullable=False)

    def __repr__(self):
        return f"<Users(SteamID64='{self.SteamID64}', disc_user='{self.disc_user}')>"

class Apps(Base):
    __tablename__ = 'applications'
    id = Column(Integer, primary_key=True)
    applicant = Column(String, nullable=False)
    status = Column(String, nullable=False)
    steamID_row = Column(Integer)
    current_question = Column(Integer)
    open_date = Column(DateTime)

    def __repr__(self):
        return f"<Apps(id='{self.id}', applicant='{self.applicant}', status='{self.status}')>"

class Questions(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey(Apps.id, ondelete='CASCADE'))
    qnum = Column(Integer, nullable=False)
    question = Column(String)
    answer = Column(String)
    # relationships
    application = relationship('Apps', backref=backref("questions", cascade="all, delete"))

    def __repr__(self):
        return f"<Qustions(id='{self.id}', qnum='{self.qnum}')>"

class BaseQuestions(Base):
    __tablename__ = 'base_questions'
    id = Column(Integer, primary_key=True)
    txt = Column(String)
    has_steamID = Column(Boolean, default=False)

    def __repr__(self):
        return f"<BaseQuestions(id='{self.id}')>"

# create the supplemental db
engineSupplemental = create_engine(cfg.SUPP_DB_PATH)
Base.metadata.create_all(engineSupplemental)

# create the Supplemental db session
SessionSupplemental = sessionmaker(bind=engineSupplemental)
sessionSupp = SessionSupplemental()

class Characters(Base):
    __tablename__ = 'characters'
    playerId = Column(String, primary_key=True)
    id = Column(Integer, nullable=False)
    char_name = Column(String, nullable=False)
    level = Column(Integer)
    rank = Column(Integer)
    guild = Column(Integer)
    isAlive = Column(Boolean)
    killerName = Column(String)
    lastTimeOnline = Column(Integer)
    killerId = Column(String)
    lastServerTimeOnline = Column(Float)

    def __repr__(self):
        return f"<Characters(playerId='{self.playerId}', id='{self.id}', char_name='{self.char_name}', level='{self.level}', rank='{self.rank}', guild='{self.guild}', isAlive='{self.isAlive}', killerName='{self.killerName}', lastTimeOnline='{self.lastTimeOnline}', killerId='{self.killerId}', lastServerTimeOnline='{self.lastServerTimeOnline}')>"

engineGame = create_engine(cfg.GAME_DB_PATH)
SessionGame = sessionmaker(bind=engineGame)
