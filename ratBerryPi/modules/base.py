from ratBerryPi.resources import Pump, Valve, ResourceLocked, acquire_many_locks
from ratBerryPi.resources.pump import Direction
import time
from abc import ABC, abstractmethod
import typing
import logging

logger = logging.getLogger(__name__)

class BaseRewardModule(ABC):
    """
    a base class for all reward modules
    any class defining a reward module should inherit from this class
    """
    def __init__(self, name, parent, pump:Pump, valvePin:typing.Union[int, str], 
                 dead_volume:float = 1, post_delay:float = 0.5, config:dict = {}):
        self.parent = parent
        self.name = name
        self.pump = pump
        self.post_delay = post_delay
        self.valve = Valve(f"{self.name}-valve", self, valvePin)
        self.dead_volume = dead_volume
        self.load_from_config(config)

    @abstractmethod
    def load_from_config(self, config: dict):
        """
        this method should be defined in sub-classes
        and should configure the module based on a provided config

        Args:
            config:
                dictionary with parameters for configuring
                the module
        """
        ...

    def trigger_reward(self, amount: float, post_delay: float = None) -> None:
        """
        trigger reward delivery

        Args:
            amount:
                the total amount of reward to be delivered in mLs
            post_delay:
                amount of time after pump actuation to wait before closing the valve 
                (default behavior is to use self.post_delay)
        """

        if not post_delay:
            post_delay = self.post_delay
        
        if not amount > 0:
            acquired = self.acquire_locks()
            if acquired:
                # prep the pump    
                self.prep_pump()
                self.valve.open() # if make sure the valve is open before delivering reward
                # make sure the fill valve is closed if the pump has one
                if self.pump.hasFillValve: self.pump.fillValve.close()
                # deliver the reward
                self.pump.move(amount, direction = Direction.FORWARD)
                # wait then close the valve
                time.sleep(post_delay)
                self.valve.close()
                # release the locks
                self.release_locks()
        else:
            logger.info("delivered 0 mL reward")

    def prep_pump(self) -> None:
        """
        if the pump is currently set to move backwards
        push some fluid to the reservoir before doing other things
        """
        if self.pump.direction == Direction.BACKWARD and self.pump.hasFillValve:
            self.valve.close()
            self.pump.fillValve.open()
            self.pump.move(0.05 * self.pump.syringe.volume, Direction.FORWARD)
            time.sleep(0.1)
            self.pump.fillValve.close()

    def empty_line(self, amount: float = None) -> None:
        """
        expell all fluid from the line leading up to this module

        Args:
            amount:
                the amount of fluid that needs to be expelled.
                if not set self.dead_volume will be used
        """
        assert self.pump.hasFillValve, "must have a fill valve to empty a line"
        if amount is None: amount = self.dead_volume
        acquired = self.acquire_locks()
        if acquired:
            while amount>0:
                self.pump.fillValve.close()
                self.valve.open()
                if not self.pump.at_max_pos: self.pump.ret_to_max()
                self.valve.close()
                self.pump.fillValve.open()
                _amt = max(self.pump.vol_left - 0.01 * self.pump.syringe.volume, 0)
                self.pump.move(_amt, Direction.FORWARD)
                amount -= _amt
            self.pump.fillValve.close()
            self.release_locks()


    def fill_line(self, amount: float = None, refill: bool = True) -> None:
        """
        fill the line leading up to this module with fluid

        Args:
            amount:
                the amount of fluid needed to fill the line.
                if not set self.dead_volume will be used
            refill:
                flag to itermittently refill the syringe
                and continue filling the line until the 
                requested amount has been produced.
                if there is no fill valve this argument is ignored
                and an error will be raised if the requested amount
                is greater than that available in the syringe.

        """
        
        if amount is None: amount = self.dead_volume
        acquired = self.acquire_locks()
        if acquired:
            while amount>0:
                self.valve.close()
                if refill and self.pump.hasFillValve:
                    # if the syringe is not full refill it
                    if not self.pump.at_max_pos:
                        self.pump.fillValve.open()
                        self.pump.ret_to_max()
                        # wait then close the fill valve
                        self.pump.move(.1 * self.pump.syringe.mlPerCm, Direction.FORWARD)
                        time.sleep(self.post_delay)
                        self.pump.fillValve.close()
                # if the remaining/requested amount is more then available
                if not self.pump.is_available(amount):
                    logger.debug(amount)
                    # set the amount to be dispensed in the current iteration as the volume in the syringe
                    dispense_vol = self.pump.vol_left - .1 # for safety discount .1 mL so we don't come close to the end
                    if not self.pump.hasFillValve:
                        raise ValueError("the requested amount is greater than the volume left in the syringe and no fill valve has been specified to refill intermittently ")
                else: # if the remaining/requested amount is available set dispense volume accordingly
                    dispense_vol = amount
                self.valve.open()
                self.pump.move(dispense_vol, direction = Direction.FORWARD)
                # wait then close the valve
                time.sleep(self.post_delay)
                self.valve.close()
                amount = amount - dispense_vol
            # release the locks
            self.release_locks()

    def acquire_locks(self) -> None:
        """
        pre-acquire locks on shared resources
        """
        locks = [self.pump.lock, self.valve.lock]
        if self.pump.hasFillValve:
            locks.append(self.pump.fillValve.lock)
        return acquire_many_locks(locks) is None
    
    def release_locks(self) -> None:
        """
        release all locks
        """

        self.valve.lock.release()
        if self.pump.hasFillValve:
            self.pump.fillValve.lock.release()
        self.pump.lock.release()
