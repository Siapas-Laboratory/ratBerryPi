import threading
import RPi.GPIO as GPIO
import logging
from datetime import datetime
import os
import typing
import yaml

class BaseInterface:
    
    def __init__(self, on:threading.Event, config_file:typing.Union[str, bytes, os.PathLike],
                 data_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "data")):
        
        GPIO.setmode(GPIO.BCM)
        self.on = on if on else threading.Event()
        
        if config_file:
            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f)

        self.recording = False
        self.data_dir = data_dir
        self.logger = logging.getLogger(__name__)

        # placeholder for file handler
        self.log_fh = None
        # create formatter
        self.formatter = logging.Formatter('%(asctime)s.%(msecs)03d, %(levelname)s, %(message)s',
                                           "%Y-%m-%d %H:%M:%S")

    def start(self):
        if not self.on.is_set(): self.on.set()

    def record(self):
        self.stop_recording()
        fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.csv")
        data_path= os.path.join(self.data_dir, fname)
        self.log_fh = logging.FileHandler(data_path)
        self.log_fh.setLevel(logging.INFO)
        self.log_fh.setFormatter(self.formatter)
        self.logger.addHandler(self.log_fh)

    def stop_recording(self):
        if self.log_fh: 
            self.logger.removeHandler(self.log_fh)

    def stop(self):
        self.stop_recording()
        GPIO.cleanup()