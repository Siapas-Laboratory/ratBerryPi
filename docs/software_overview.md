# Software Overview
## Architecture
RatBerryPi consists of 3 layers of abstraction: the reward interface, reward modules and resources. The interface orchestrates use of all modules and resources. Resources are considered to be devices such as a syringe pump or solenoid valve that may or may not be shared accross modules. Modules are collections or resources. Importantly, the module must have associated to it a valve which can be opened to direct the flow of fluid to it. In the default use case, the interface has associated to it a set of pumps which several reward modules share. Each module has a valve, an led, a lickometer and a speaker associated to it.

**Technical Notes**
#TODO: add some info here about how the multi-speaker control is implemented in hardware and what this means for how the speakers are controlled and also the lickometer bus

## Configuration
This package includes a default configuration file `default-config.yaml` which reserves GPIO pins and pins on the GPIO expander to control up to 8 of our custom modules. Users may specify a custom configuration file by creating a file called `.ratBerryPi-config.yaml` and placing it in the home directory of the pi (i.e. the file should have path `~/.ratBerryPi-config.yaml`). At a minimum, the configuration must specify the fields `modules` and `pumps`. `modules` should should have sub-fields corresponding to module names and each sub-field should have corresponding sub-fields with configuration parameters for that module. Pump parameters should be specified equivalently under `pumps`. Below we detail necessary parameters for pump and module configuration:

### Module Configuration
Modules may be considered either using presets or from scratch. When configuring modules from scratch, users must specify the module `type` along with any relevant parameters for that module type. Default modules, for example, are specified by "type: DefaultModule" and require the following parameters

* `LEDPin`: GPIO pin that controls this module's LED
* `lickPin`: GPIO pin monitoring licks on this module
* `SDPin`:  GPIO pin that gates audio played on this module's speaker
* `valvePin`: GPIO pin that will control the valve that gates reward delivery to this module
* `dead_volume` *(optional)* : dead volume in tubing leading up to the module
* `lickBusPin`: GPIO pin that reads the interupt signal from the bus associated to this lickometer
* `pump` - the name of the pump feeding into this reward module

Note that GPIO pins on the GPIO expander must be specified by the expander's hexadecimal address first followed by the pin name (e.g `0x21:GPA0` for pin A0 on the expander at address 0x21). As noted below, `pump` and `valve_pin` are required arguments for all module types. 

Users may specify a `preset_name` to configure a module according to preset pin mappings specified in `presets.yaml`. Any parameters not specified in the preset must be specified in the config file.

#### Custom Modules
For users that would like to create custom reward modules you will need to define the module under the `ratBerryPi/interfaces/reward/modules` folder by sub-classing the BaseRewardModule class (see `ratBerryPi/interfaces/reward/modules/default.py` for an example). Importantly, the user must define a method `load_from_config` in the sub-class which should take as input a dictionary with configuration parameters for the module (such as pin mappings) and instantiate any resources the module needs as necessary. This dictionary will come from the `config.yaml` file. For any custom module type, users must specify a pump and valvePin.

### Pump Configuration

When configuring a pump, one must specify the following fields

* `port` : usb port address for communicating with the pico that controls the pump
* `lead` : lead of the lead screw in cm
* `syringeType` *(optional)* -The type of syringe that will be loaded on the pump by default. Current options include: BD1mL, BD5mL, BD10mL, BD30mL, BD50/60mL. Note, these options refer to keys in a dictionary called `syringeTypeDict` defined in the `Syringe` class in `pump.py`. Users may add additional syringes by adding new entries to this dictionary with the inner diameter of a given syringe and the maximum length the syringe can be withdrawn to when loaded on the pump (in cm).
* `fillValvePin` *(optional)* - A pin on the raspberry pi to control a valve attached to reservoir. This valve, if specified, will be used to allow fluid to be drawn into the syringe from the reservoir

### Plugins

Users may optionally specify resources that are not attached to a module which we refer to here as "plugins". Under `plugins` the user should specify unique names for each individual plugin used in the device. Under these names the user should further indicate any relevant key word arguments that would be needed to instantiate the plugin's associated class

 ## Developer Notes
 We encourage users to clone the repository and customize the code to their needs. To define a new resource sub-class the BaseResource class in the ratBerryPi/resources folder and define the class in a file in the same folder. Note, in the interest of thread safety, the BaseResource class when initialized has an attribute `lock` which is a re-entrant lock (see [here](https://docs.python.org/3/library/threading.html#rlock-objects) for details). We recommend developers to use this lock as a way to reserve resources in case multiple clients try to access it. To create a new module simply sub-class the BaseModule class under ratBerryPi/modules and define the class within a file you create in this same folder. Importantly this BaseModule class is an abstractbaseclass which expects the user to define a load_from_config method in the subclass which will configure the module instance using a config specified as a dict which is loaded from each module field within the config file. For an example see the default module. After making any changes you can reinstall the ratBerryPi by navigating to the root directory of the repo and running `pip3 install .`
