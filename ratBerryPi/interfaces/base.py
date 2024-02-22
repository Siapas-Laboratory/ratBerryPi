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
            if 'clockPin' in self.config:
                self.clockPin = self.config['clockPin']
                GPIO.setup(self.clockPin, GPIO.IN, GPIO.PUD_OFF)
                GPIO.add_event_detect(self.clockPin, GPIO.RISING, callback=self.log_clk_signal)

        self.recording = False
        self.data_dir = data_dir
        self.logger = logging.getLogger(__name__)

        # placeholder for file handler
        self.log_fh = None
        # create formatter
        self.formatter = logging.Formatter('%(asctime)s.%(msecs)03d, %(levelname)s, %(message)s',
                                           "%Y-%m-%d %H:%M:%S")

    def log_clk_signal(self, x):
        self.logger.info("clock")

    def start(self):
        if not self.on.is_set(): self.on.set()

    def record(self, data_dir = None):
        data_dir = data_dir if data_dir else self.data_dir
        os.makedirs(data_dir, exist_ok = True)
        self.stop_recording()
        log_fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.csv")
        self.data_path = os.path.join(data_dir, log_fname)
        self.log_fh = logging.FileHandler(self.data_path)
        self.log_fh.setLevel(logging.INFO)
        self.log_fh.setFormatter(self.formatter)
        self.logger.addHandler(self.log_fh)

    def stop_recording(self):
        if self.log_fh: 
            self.logger.removeHandler(self.log_fh)

    def stop(self):
        self.stop_recording()
        GPIO.cleanup()