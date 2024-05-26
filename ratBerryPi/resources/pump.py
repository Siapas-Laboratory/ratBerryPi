from .base import BaseResource, ResourceLocked
from .valve import Valve
import time
import math
import threading
import os
import time
from enum import Enum
from PyQt5.QtCore import pyqtSignal, QObject
import serial

class Direction(Enum):
    FORWARD="F"
    BACKWARD="B"

class EndTrackError(Exception):
    """reached end of track"""
    pass

class PumpNotEnabled(Exception):
    pass

class IncompleteDelivery(Exception):
    """could not reach goal"""
    pass
    
class Syringe:
    # ID and volume for any syringes we might want to use
    # in cm and mL respectively 
    syringeTypeDict = {'BD1mL':     {'ID': 0.478, 'volume': 1}, 
                       'BD5mL':     {'ID': 1.207, 'volume': 5},
                       'BD10mL':    {'ID': 1.45,  'volume': 10},
                       'BD30mL':    {'ID': 2.17,  'volume': 30},
                       'BD50mL':    {'ID': 2.67,  'volume': 50}}

    def __init__(self, syringeType = 'BD10mL'):
        self.syringeType = syringeType

    @property
    def syringeType(self):
        return self._syringeType

    @syringeType.setter
    def syringeType(self, syringeType):
        if not syringeType in self.syringeTypeDict:
            msg = f"invalid syringeType '{syringeType}'. valid syringes include {[i for i in self.syringeTypeDict]}"
            raise ValueError(msg)
        self._syringeType = syringeType

    @property
    def ID(self):
        return self.syringeTypeDict[self.syringeType]['ID']

    @property
    def volume(self):
        return self.syringeTypeDict[self.syringeType]['volume']
    
    @property
    def max_pos(self):
        return self.volume/(math.pi * (self.ID/2)**2)
    
    @property
    def mlPerCm(self):
        return math.pi * ((self.ID/2)**2)

class PositionUpdater(QObject):
    pos_updated = pyqtSignal(float)

class Pump(BaseResource):

    step_types = ['Full', 'Half', '1/4', '1/8', '1/16', '1/32']
    steps_per_rev = [200, 400, 800, 1600, 3200, 6400]

    
    def __init__(self, name, port:str, parent = None, fillValvePin = None, lead = 0.2,
                 syringe:Syringe = Syringe(syringeType='BD5mL'), baudrate:int = 230400):
        
        """
        this is a class that allows for the control of a syringe
        pump actuated by a Nema 17 Bipolar stepper motor and driven
        by a DRV8825 via a raspberry pi. NOTE: we are not using RPIMotorLib
        because we needed some functionality to track the position of the pump
        but many of the provided functions are heavily inspired by RPIMotorLib
        
        Args:
        -----
        """

        super(Pump, self).__init__(name, parent)
        self.syringe = syringe
        if fillValvePin is not None:
            self.fillValve = Valve(f'{self.name}-fillValve', self, fillValvePin)
            self.hasFillValve = True
        else:
            self.hasFillValve = False
        self.serial = serial.Serial(port, baudrate = baudrate)
        self.serial_lock = threading.Lock()
        self.position = 0
        self.monitor_thread = threading.Thread(target = self._monitor)
        self.monitor_thread.start()
        self.pos_updater = PositionUpdater()
        self._speed = None
        self._stepType = None
        self.lead = lead
    @property
    def direction(self):
        return self._direction
    
    @property
    def flow_rate(self):
        steps_per_rev = self.steps_per_rev[self.step_types.index(self.stepType)]
        cm_per_step = self.lead/steps_per_rev
        cm_per_sec = self.speed * cm_per_step
        flow_rate = self.syringe.mlPerCm * cm_per_sec
        return flow_rate
    
    @direction.setter
    def direction(self, direction):
        if not isinstance(direction, Direction):
            raise ValueError("direction must be of type 'Direction'")
        self._direction = direction

    @property
    def syringe(self):
        return self._syringe

    @syringe.setter
    def syringe(self, syringe):
        assert isinstance(syringe, Syringe), 'syringe must be an instance of Syringe'
        self._syringe = syringe
    
    @property
    def at_min_pos(self):
        return self.position <= 0

    @property
    def at_max_pos(self):
        return self.position >= self.syringe.max_pos

    @property
    def vol_left(self):
        return math.pi * ((self.syringe.ID/2)**2) * self.position
    
    @property
    def stepType(self):
        return self._stepType
    
    @stepType.setter
    def stepType(self, stepType):
        if stepType in self.step_types:
            self.send_command("SETTING", setting="MICROSTEP", value=stepType)
        else:
            raise ValueError(f"invalid step type. valid stepTypes include {[i for i in self.step_types]}")
    
    @property
    def speed(self):
        return self._speed
    
    @speed.setter
    def speed(self, speed):
        assert isinstance(speed, float)
        self.send_command("SETTING", setting="SPEED", value=speed)

    def _monitor(self):
        os.nice(19)
        while not self.parent.on.is_set(): time.sleep(.001)
        while self.parent.on.is_set():
            while self.serial.in_waiting:
                acq = self.serial_lock.acquire(False)
                if acq:
                    res = self.serial.readline().decode().strip().split(',')
                    self.serial_lock.release()
                    if len(res) == 6:
                        try:
                            pos, running, direction, move_complete, step_lvl, speed = res
                            pos = float(pos)
                            if pos != self.position:
                                self.position = pos
                                self.pos_updater.pos_updated.emit(self.position)
                            self.running = int(running) == 1
                            self.direction = Direction.FORWARD if int(direction) == 1 else Direction.BACKWARD
                            self.move_complete = int(move_complete) == 1
                            self._stepType = self.step_types[int(step_lvl)]
                            self._speed = float(speed)
                        except:
                            pass
                time.sleep(.05)

        self.serial.close()

                
    def calibrate(self, channel=None):
        self.send_command("CALIBRATE")

    def send_command(self, mode:str, setting:str = None, value:float = None, direction:Direction = None, distance:float = None) -> None:
        """
        send command to the arduino
        """

        acq = self.serial_lock.acquire(timeout = 5)
        
        if not acq:
            raise ResourceLocked("Serial port in use")
        if mode == "RUN":
            if not isinstance(direction, Direction): 
                raise ValueError("must specify direction using Direction class when using RUN mode")
            direction = direction.value
            if not isinstance(distance, (int, float)): 
                raise ValueError("must specify distance as float when using RUN mode")
            distance = str(distance)
            setting = "NULL"
            value = "NULL"
        elif mode == "SETTING":
            if not isinstance(setting, str):  
                raise ValueError("must specify the setting to set as float or int")
            if setting == "MICROSTEP":
                if value not in self.step_types: 
                    raise ValueError("unrecognized step type")
                value = str(self.step_types.index(value))
            else:
                if not isinstance(value, (int, float)):  
                    raise ValueError("must specify the value to set as float or int")
                value = str(value)
            distance = "NULL"
            direction = "NULL"
        elif mode in ["CALIBRATE", "STOP", "CLEAR"]:
            setting = "NULL"
            value = "NULL"
            distance = "NULL"
            direction = "NULL"
        else:
            raise ValueError(f"unrecognized command {mode}")

        cmd = ",".join(["<",mode, setting, value, direction, distance,">"])

        self.serial.write(cmd.encode())
        self.serial.flushInput()
        self.serial_lock.release()

    
    def is_available(self, amount, direction = Direction.FORWARD):
        if direction == Direction.FORWARD:
            return amount < self.vol_left
        else:
            return amount <= (math.pi * ((self.syringe.ID/2)**2) * self.syringe.max_pos) - self.vol_left
            

    def move(self, amount, direction, check_availability = True, 
             blocking = False, timeout = -1):
        """
        move a given amount of fluid out of or into the syringe
        
        Args:
        -----
        amount: float
            desired fluid output in mL
        forward: bool
            whether or not to move the piston forward
        """
        if amount >0:
            acq = self.lock.acquire(blocking = blocking, timeout = timeout)
            if self.running or not acq:
                raise ResourceLocked("Pump in use")
            else:
                if check_availability:
                    if not self.is_available(amount, direction):
                        self.lock.release()
                        raise EndTrackError

                pre_pos = self.position
                dist = amount / self.syringe.mlPerCm
                dir_int = 1 if direction == Direction.FORWARD else -1
                target = pre_pos - dir_int*dist
                ok_error = 0.01 * self.syringe.max_pos

                self.logger.debug(f"target position: {target} cm")
                self.logger.debug(f"allowable error: {ok_error} cm")

                self.send_command("CLEAR")
                while self.move_complete: time.sleep(0.05)
                self.send_command("RUN", direction = direction, distance = dist)
                while not self.move_complete: time.sleep(0.1)

                self.logger.debug(f"final position: {self.position} cm")
                err = abs(self.position - target)
                self.logger.debug(f"error: {err} cm")
                if err>ok_error:
                    self.lock.release()
                    raise IncompleteDelivery
                self.lock.release()

    def ret_to_max(self, blocking = False, timeout = -1):
        if not self.at_max_pos:
            amount = self.syringe.volume - self.vol_left
            self.move(amount, direction = Direction.BACKWARD,
                      blocking = blocking, timeout = timeout)
        else:
            raise EndTrackError

    def change_syringe(self, syringeType):
        """
        convenience function to change the syringe type
        """
        self.syringe = Syringe(syringeType)

    def stop(self):
        """
        stop the pump
        """
        self.send_command("STOP")

