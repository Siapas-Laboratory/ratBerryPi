import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s.%(msecs)03d, %(levelname)s, %(message)s',
                              "%Y-%m-%d %H:%M:%S")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)

log_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)
fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.log")
log_file = os.path.join(log_dir, fname)
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)