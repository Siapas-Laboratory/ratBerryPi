from abc import ABC, abstractmethod
import threading
import RPi.GPIO as GPIO
import logging
from datetime import datetime
import os

class BaseInterface:
    
    def __init__(self, on:threading.Event, data_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "data")):
        super(BaseInterface, self).__init__()
        GPIO.setmode(GPIO.BCM)
        self.on = on
        self.recording = False
        self.data_dir = data_dir
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)

        # placeholder for file handler
        self.data_log_fh = None

        # create handler for logging to the console
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handler
        self.formatter = logging.Formatter('%(asctime)s.%(msecs)03d, %(levelname)s, %(message)s',
                                           "%Y-%m-%d %H:%M:%S")
        ch.setFormatter(self.formatter)
        # add the handlers to the logger
        self.logger.addHandler(ch)

    def start(self):
        if not self.on.is_set(): self.on.set()

    def record(self):
        self.stop_recording()
        fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.csv")
        data_path= os.path.join(self.data_dir, fname)
        self.log_fh = logging.FileHandler(data_path)
        self.log_fh.setLevel(logging.DEBUG)
        self.log_fh.setFormatter(self.formatter)
        self.logger.addHandler(self.log_fh)

    def stop_recording(self):
        if self.log_fh: 
            self.logger.removeHandler(self.log_fh)

    def stop(self):
        self.stop_recording()
        GPIO.cleanup()

    