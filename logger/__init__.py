import os
import config as cfg
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

if not os.path.exists('logs'):
    os.mkdir('logs')
err_handler = RotatingFileHandler('logs/error.log', maxBytes=1048576, backupCount=3)
err_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
err_handler.setLevel(logging.ERROR)
logger.addHandler(err_handler)
file_handler = RotatingFileHandler('logs/bot.log', maxBytes=1048576, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
logger.setLevel(cfg.LOG_LEVEL)
logger.addHandler(file_handler)
