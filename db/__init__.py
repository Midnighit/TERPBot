from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import config as cfg

# setup the metadata
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    SteamID64 = Column(String(17), unique=True, nullable=False)
    disc_user = Column(String, unique=True, nullable=False)

    def __repr__(self):
        return f"<User(SteamID64='{self.SteamID64}', disc_user='{self.disc_user}')>"

# create the User table
engineUser = create_engine('sqlite:///users.db')
Base.metadata.create_all(engineUser)

# create the User table session
SessionUser = sessionmaker(bind=engineUser)
sessionUser = SessionUser()

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
