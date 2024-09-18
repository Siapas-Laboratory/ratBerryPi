# Software Overview
## Architecture
RatBerryPi consists of 3 layers of abstraction: the reward interface, reward modules and resources. The interface orchestrates use of all modules and resources. Resources are considered to be devices such as a syringe pump or solenoid valve which we may want to actuate and may be shared accross modules. Modules are collections or resources some of which may be unique to that module. Importantly, the module must have associated to it a valve which can be actuated to direct the flow of fluid to it. In the default use case, the interface has associated to it a set of pumps which several reward modules share. Each module has a valve, an led, a lickometer and a speaker associated to it.

**Technical Notes**
#TODO: add some info here about how the multi-speaker control is implemented in hardware and what this means for how the speakers are controlled and also the lickometer bus


## Configuration
This package includes a default configuration file which reserves GPIO pins and pins on the GPIO expander to control up to 8 of our custom modules. For users that would like to create custom reward modules you will need to define the module under the `ratBerryPi/interfaces/reward/modules` folder by sub-classing the BaseRewardModule class (see `ratBerryPi/interfaces/reward/modules/default.py` for an example). Importantly, the user must define a method `load_from_config` in the sub-class which should take as input a dictionary with configuration parameters for the module (such as pin mappings) and instantiate any resources the module needs as necessary. This dictionary will come from the `config.yaml` file where it is represented as the sub-fields of a given module listed under the `modules` section. As such, these sub-fields in the config file must be specified as needed for the configuration of the module in your `load_from_config` method. Some other required sub-fields for each module are as follows:

* `type` - the name of your custom reward module class
* `pump` - the name of the pump feeding into this reward module class
 * `valvePin`- a pin on the raspberry pi for controlling the valve on the manifold which routes reward to this module
 * `dead_volume` *(optional)* - the dead volume of the line leading up to the module in mL.

The other important fields of the config file are `pumps` and `plugins`.  Under `pumps`, the user must specify names for all pumps that will be controlled by the interface. Further, under each pump's name, one must specify the following fields, which mostly reference the pinout for the DRV8825, the driver for stepper motor actuating the pump.

* `stepPin` - The pin on the raspberry pi connected to the STEP pin of the driver
* `stepType` - The type of microstepping to use when stepping the motor. Either Full, Half, 1/4, 1/8, or 1/16.
* `flushPin` - A pin on the raspberry pi connected to a button to be used to manually progress the pump forward
* `revPin` - A pin on the raspberry pi connected to a button to be used to manually progress the pump backwards
* `dirPin` -  The pin on the raspberry pi connected to the DIR pin of the driver
* `modePins` - A list of pins on the raspberry pi connected to the M0, M1 and M2 pins on the driver in that order.
* `syringeType` *(optional)* -The type of syringe that will be loaded on the pump by default. Current options include: BD1mL, BD5mL, BD10mL, BD30mL, BD50/60mL. Note, these options refer to keys in a dictionary called `syringeTypeDict` defined in the `Syringe` class in `pump.py`. Users may add additional syringes by adding new entries to this dictionary with the inner diameter of a given syringe and the maximum length the syringe can be withdrawn to when loaded on the pump (in cm).
* `fillValvePin` *(optional)* - A pin on the raspberry pi to control a valve attached to reservoir. This valve, if specified, will be used to allow fluid to be drawn into the syringe from the reservoir

*Pinout for the driver:*

![DRV8825 pinout](https://a.pololu-files.com/picture/0J4232.600.png?f2f6269e0a80c41f0a5147915106aa55)


Under `plugins` the user should specify unique names for each individual plugin used in the device. Under these names the user should further indicate any relevant arguments for specifying the plugin. All plugins should specify the argument `type`. See the provided config file for arguments required of already implemented plugins. When defining a new plugin be sure to create a file with a class definition for an object to control the plugin. Furthermore, be sure to implement logic for creating and instance of this class in the init function for `RewardInterface` in `reward.py` when parsing the config file. 

 Finally, under `modules`, the user should specify names for the modules that will be included on the interface. Under each name, the user must then indicate the following

 * `pump` - the name of the pump feeding into this reward module
 * `valvePin` *(optional)* - a pin on the raspberry pi for controlling the valve on the manifold which routes reward to this module
 * `plugins` - an enumerated list of all plugins attached to this module. the keys should be general names for what the plugin is to the given module. Generally, this will might be the plugin type. For example, we may attach lickometer1 to module1 by specifying the `plugins` field of module1 as follows:

 ```
 plugins:
    lickometer1:
         type: Lickometer
         lickPin: 10
 ```


 The only constraint in configuring reward modules is that each module must specify a single pump that it is attached to and, optionally, a pin for controlling the valve on the manifold which feeds the port. The pump need not be unique to each module, but the valves should be unique. Indeed, in the design detailed here, all modules share a pump.

 ## Developer Notes
 We encourage users to clone the repository and customize the code to their needs. To define a new resource sub-class the BaseResource class in the ratBerryPi/resources folder and define the class in a file in the same folder. Note, in the interest of thread safety, the BaseResource class when initialized has an attribute `lock` which is a re-entrant lock (see [here](https://docs.python.org/3/library/threading.html#rlock-objects) for details). We recommend developers to use this lock as a way to reserve resources in case multiple clients try to access it. To create a new module simply sub-class the BaseModule class under ratBerryPi/modules and define the class within a file you create in this same folder. Importantly this BaseModule class is an abstractbaseclass which expects the user to define a load_from_config method in the subclass which will configure the module instance using a config specified as a dict which is loaded from each module field within the config file. For an example see the default module. After making any changes you can reinstall the ratBerryPi by navigating to the root directory of the repo and running `pip3 install .`
