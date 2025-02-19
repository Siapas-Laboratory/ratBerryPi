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
from typing import Union, Dict, List

class Direction(Enum):
    """directions of the pump"""
    FORWARD="F"
    BACKWARD="B"

class EndTrackError(Exception):
    """reached end of track"""
    pass

class PumpNotEnabled(Exception):
    """pump is not enabled"""
    pass

class IncompleteDelivery(Exception):
    """could not reach goal"""
    pass
    
class Syringe:
    """
    a syringe which may be loaded in the pump
    """


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
    def syringeType(self) -> str:
        """
        name of the type of syringe
        """
        return self._syringeType

    @syringeType.setter
    def syringeType(self, syringeType):
        if not syringeType in self.syringeTypeDict:
            msg = f"invalid syringeType '{syringeType}'. valid syringes include {[i for i in self.syringeTypeDict]}"
            raise ValueError(msg)
        self._syringeType = syringeType

    @property
    def ID(self) -> float:
        """
        inner diameter of the syringe in cm
        """
        return self.syringeTypeDict[self.syringeType]['ID']

    @property
    def volume(self) -> float:
        """
        max volume of this syringe in mL
        """
        return self.syringeTypeDict[self.syringeType]['volume']
    
    @property
    def max_pos(self) -> float:
        """
        maximum possible position the pump can assume
        while this syringe is loaded (cm)
        """
        return self.volume/(math.pi * (self.ID/2)**2)
    
    @property
    def mlPerCm(self) -> float:
        """
        mL of fluid per cm displacement of the piston
        of this syringe
        """
        return math.pi * ((self.ID/2)**2)

class PositionUpdater(QObject):
    """
    QObject used to signal to a GUI that the 
    position has been updated
    """
    pos_updated = pyqtSignal(float)

class Pump(BaseResource):
    """
    this is a class that allows for the control of a syringe
    pump actuated by a Nema 17 Bipolar stepper motor and driven
    by a DRV8825 via a raspberry pi pico which we interface with
    over a serial bus
    """

    step_types = ['Full', 'Half', '1/4', '1/8', '1/16', '1/32']
    steps_per_rev = [200, 400, 800, 1600, 3200, 6400]

    
    def __init__(self, name: str, port: str, parent = None, fillValvePin: Union[str, int] = None, 
                 lead: float = 0.2, syringe: Syringe = Syringe(syringeType='BD5mL'), baudrate: int = 230400):
        
        """
        Args:
            name:
                name to assign the pump
            port: 
                serial port to listen and write to
                when communicating with the pico
            parent:
                parent reward interface which this pump is attached to
            fillValvePin: 
                GPIO pin to use to programmatically toggle the fill valve
            lead:
                lead of the lead screw in cm. this should match the value
                set on the pico
            syringe:
                syringe that should be loaded in the pump at the start
            baudrate:
                baudrate for communicating with the pico

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
    def direction(self) -> Direction:
        """
        direction the pump is set to move in
        """
        return self._direction
    
    @property
    def flow_rate(self) -> float:
        """
        flow rate in ml/s
        """
        steps_per_rev = self.steps_per_rev[self.step_types.index(self.stepType)]
        cm_per_step = self.lead/steps_per_rev
        cm_per_sec = self.speed * cm_per_step
        flow_rate = self.syringe.mlPerCm * cm_per_sec
        return flow_rate
    
    @direction.setter
    def direction(self, direction: Direction) -> None:
        if not isinstance(direction, Direction):
            raise ValueError("direction must be of type 'Direction'")
        self._direction = direction

    @property
    def syringe(self) -> Syringe:
        """
        syringe loaded in the pump
        """
        return self._syringe

    @syringe.setter
    def syringe(self, syringe: Syringe) -> None:
        assert isinstance(syringe, Syringe), 'syringe must be an instance of Syringe'
        self._syringe = syringe
    
    @property
    def at_min_pos(self) -> bool:
        """
        flag indicating if the pump is at or below
        it's minimum position
        """
        return self.position <= 0

    @property
    def at_max_pos(self) -> bool:
        """
        flag indicating if the pump is at or beyond
        it's maximum position given the syringe
        """
        return self.position >= self.syringe.max_pos

    @property
    def vol_left(self) -> float:
        """
        amount of fluid left in the syringe on the pump (mL)
        """
        return math.pi * ((self.syringe.ID/2)**2) * self.position
    
    @property
    def stepType(self) -> str:
        """
        micro stepping type used by the motor on the pump
        """
        return self._stepType
    
    @stepType.setter
    def stepType(self, stepType: str) -> None:
        if stepType in self.step_types:
            self.send_command("SETTING", setting="MICROSTEP", value=stepType)
        else:
            raise ValueError(f"invalid step type. valid stepTypes include {[i for i in self.step_types]}")
    
    @property
    def speed(self) -> float:
        """
        step speed of the motor on the pump (steps/s)
        """
        return self._speed
    
    @speed.setter
    def speed(self, speed: float) -> None:
        assert isinstance(speed, float)
        self.send_command("SETTING", setting="SPEED", value=speed)

    def _monitor(self) -> None:
        os.nice(19)
        while not self.parent.on.is_set(): time.sleep(.001)
        self.running = False
        self.move_complete = False
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
                            r = int(running) == 1
                            if r != self.running:
                                self.running =r
                                self.logger.debug(f'running is {r}')
                            self.direction = Direction.FORWARD if int(direction) == 1 else Direction.BACKWARD
                            mc = int(move_complete) == 1
                            if mc != self.move_complete:
                                self.move_complete = mc
                                self.logger.debug(f'move_complete is {mc}')
                            self._stepType = self.step_types[int(step_lvl)]
                            self._speed = float(speed)
                        except:
                            pass
                time.sleep(.05)

        self.serial.close()

                
    def calibrate(self) -> None:
        """
        zero the pump position
        """
        self.send_command("CALIBRATE")

    def send_command(self, mode: str, setting: str = None, value: float = None, 
                     direction: Direction = None, distance: float = None) -> None:
        """
        send a command to the pico

        Args:
            mode:
                the command to run through the pico. available 
                modes are as follows:
                    RUN: move the pump a specified distance (must pass the distance argument) 
                    SETTING: set a parameter on the pump
                    CALIBRATE: zero the position of the pump carriage sled
                    STOP: stop the pump if it is currently moving to a target
                    CLEAR: clear the move complete flag so it can be raised again when a run is finished
            setting:
                name of parameter to set if mode is SETTING
            value:
                value to set setting to if mode is SETTING
            direction:
                direction to move the pump carriage sled if the mode is RUN
            distance:
                distance to move the pump carriage sled in cm if the mode is RUN
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

    
    def is_available(self, amount: float, direction: Direction = Direction.FORWARD) -> bool:
        """
        returns a bool indicating if the specified amount of fluid is available in
        the syringe if direction is forward or can be drawn into the syringe if direction
        is backwards

        Args:
            amount:
                desired amount of fluid in mL
            direction:
                direction the fluid needs to be moved
        """
        if direction == Direction.FORWARD:
            return amount < self.vol_left
        else:
            return amount <= (math.pi * ((self.syringe.ID/2)**2) * self.syringe.max_pos) - self.vol_left
            

    def move(self, amount: float, direction: Direction, check_availability: bool = True, 
             blocking: bool = False, timeout: float = -1) -> None:
        """
        move a given amount of fluid out of or into the syringe
        
        Args:
            amount:
                amount of fluid to move in mL
            direction:
                direction the fluid needs to be moved
            check_availability:
                flag indicating to check whether or not 
                the specified amount is available before
                making the request to the pico. if true
                an EndTrackError will be raised if the amount
                is not available
            blocking:
                passed on to the acquire method of this pumps
                re-entrant threading lock. (see threading.RLock.acquire)
            timeout:
                passed on to the acquire method of this pumps
                re-entrant threading lock. (see threading.RLock.acquire)
        """
        if amount >0:
            acq = self.lock.acquire(blocking = blocking, timeout = timeout)
            if self.running or not acq:
                if acq: self.lock.release()
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
                to = False
                t_start = time.time()
                self.send_command("RUN", direction = direction, distance = dist)
                while (not self.running) and (not to):
                    # wait until we're actually running
                    time.sleep(0.05)
                    to = (time.time() - t_start)>1
                
                if not to:          
                    while (not self.move_complete) and self.running:
                        # wait for either the move complete flag or for running to turn off
                        # (i.e. force stop) 
                        time.sleep(0.1)
                else:
                    self.logger.warning('missed the start of pump movement')
                self.logger.debug(f"final position: {self.position} cm")
                err = abs(self.position - target)
                self.logger.debug(f"error: {err} cm")
                if err>ok_error:
                    self.lock.release()
                    raise IncompleteDelivery
                self.lock.release()

    def ret_to_max(self, blocking: bool = False, timeout: float = -1) -> None:
        """
        return the pump to the max position allowable for the syringe

        Args:
            blocking:
                passed on to the acquire method of this pumps
                re-entrant threading lock. (see threading.RLock.acquire)
            timeout:
                passed on to the acquire method of this pumps
                re-entrant threading lock. (see threading.RLock.acquire)
        """

        if not self.at_max_pos:
            amount = self.syringe.volume - self.vol_left
            self.move(amount, direction = Direction.BACKWARD,
                      blocking = blocking, timeout = timeout)
        else:
            raise EndTrackError

    def change_syringe(self, syringeType: str) -> None:
        """
        convenience function to change the type of syringe
        loaded in the pump

        Args:
            syringeType:
                new syringe type
        """
        self.syringe = Syringe(syringeType)

    def stop(self) -> None:
        """
        stop the pump
        """
        self.send_command("STOP")

