# rpi-reward-module
An extendable Raspberry Pi based device/platform for controlling multiple muli-functional reward modules. The device uses a modified version of the open source [Poseidon Syringe Pump](https://pachterlab.github.io/poseidon/) to supply fluid as reward to any of multiple reward ports via a luer manifold and an array of media isolation solenoid valves. The manifold is connected to a reservoir which the device can be programmed to intermittently draw fluid from. 

In the design detailed [here](), the modules themselves are each fitted with a lickometer, speaker and LED. The code, however, is flexible, such that users may design custom modules with additional or fewer components ("plugins") as needed. The only constraint is that each module must specify a single pump that it is attached to and, optionally, a pin for controlling the valve on the manifold which feeds the port. The pump need not be unique to each module, but the valves should be unique. Indeed, in the design detailed here, all modules share a pump. Similarly, modules may share plugins as needed.


## Software Installation - (Raspberry Pi)
To get started, if you have not already done so, install `berryconda` on the raspberry pi that will serve as the interface to the reward modules. To do this run the following commands:

```
wget https://github.com/jjhelmus/berryconda/releases/download/v2.0.0/Berryconda3-2.0.0-Linux-armv7l.sh
bash Berryconda3-2.0.0-Linux-armv7l.sh
```

From here you may need to open a new terminal. Now we will create a conda environment for this package. First clone this repository and navigate to the cloned directory. From here run the following commands

```
conda create -n reward-module
conda install -n reward-module pandas pyyaml pip
source activate reward-module
pip install -r requirements.txt
```

## Configuration
Before using the system, a `config.yaml` file must be created. This file is parsed to setup the pins on the raspberry pi. The provided `config.yaml` file contains parameters for the build detailed [here](). When defining a config file for a custom setup the 2 fields that are required at a minimum are `modules` and `pumps`. Under `pumps`, the user must specify names for all pumps that will be controlled by the interface. Under each pump's name, the following arguments must be specified:

...

 Under `modules`, the user should specify names for the modules that will be included on the interface. Under each name, the user must then indicate ...

## Usage
There are 2 main modes of operation for this platform. The Raspberry Pi can be configured as a server that clients on other machines may connect to in order to run commands as needed. Alternatively, one may write a program which creates an instance of the RewardInterface class defined in `reward.py` and invoke methods of this class to run a behavioral protocol. The help documentation for the RewardInterface class includes relevant information about it's exposed methods. Here we will elaborate on the server-client mode of operation.

### Server-Client Setup
...


## Operating the Syringe and Manifold
Before using the device all lines must be filled with the solution to be delivered to the reward ports. **The key here is making sure there are no air bubbles or at least as few as possible.** The following steps detail a fairly reliable procedure for accomplishing this

1. Start with all outlets to the reward ports blocked off on the manifold (as shown below; TODO: need a picture here). Fill the reservoir with the reward solution. 
2. Attach a syringe with the piston all the way down (i.e. completely empty) to the inlet port  and manually fill the syringe while pressing the button to open the fill valve. Make sure there are no air bubbles in the manifold.
3. Remove the syringe and empty it’s contents 
4. Refill the syringe manually from the reservoir
5. Make sure there are no air bubbles in the syringe and reattach to the inlet port. When attaching, fill the luer connector with water from the syringe so that it is overflowing before fastening. This will help to prevent air bubbles from forming.
6. Open back up the ports on the manifold that go to the reward modules (as shown below; TODO: need a picture here).
7. If you have not already done so, start up the server on the raspberry pi and connect a client. Use the ‘fill_lines’ command to fill all of the lines with water. This will sequentially open the valves for the reward modules and inject a specified amount of water. The amount should be at least as much as the dead volume in the line but no more than the syringe volume. Note, sequential filling is important here because if we open all valves to flush all at once, the valves will not  fill evenly and we may end up with air bubbles.
