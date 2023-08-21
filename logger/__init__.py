import os
import sys
import logging
from config import LOG_LEVEL
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

if not os.path.exists("logs"):
    os.mkdir("logs")
prn_handler = logging.StreamHandler(sys.stdout)
prn_handler.setLevel(LOG_LEVEL)
logger.addHandler(prn_handler)
err_handler = RotatingFileHandler("logs/error.log", maxBytes=1048576, backupCount=3, encoding='utf-8')
err_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"))
err_handler.setLevel(logging.ERROR)
logger.addHandler(err_handler)
file_handler = RotatingFileHandler("logs/bot.log", maxBytes=1048576, backupCount=3, encoding='utf-8')
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
logger.setLevel(LOG_LEVEL)
logger.addHandler(file_handler)
