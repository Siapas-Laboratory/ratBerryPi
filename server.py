import socket
from reward import RewardInterface, RewardModule
import RPi.GPIO as GPIO

#TODO: need to figure out the correct values for these
# to communicate from a pc
host = 'localhost'
port = 5560

# TODO: functions to add:
# setting all syringe types at once
# setting all ids at once
# resetting the lick count
# getting the module names
# pulling back the syringe? (on this note also need to figure out end detection)

def start_server(reward_interface):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            print('binding the port')
            sock.bind((host, port))
        except socket.error as msg:
            print(msg)
        
        while True:
            try:
                sock.listen()
                print('waiting for connections...')
                conn, _ =  sock.accept()
                print('connection accepted, waiting for data')
                while True:
                    # Receive the data
                    # should there be a timeout on this?
                    data = conn.recv(1024) # receive the data
                    command = data.decode('utf-8')
                    command = command.split(' ')

                    if len(command)==1:
                        if command[0] == "EXIT":
                            print("client disconnected")
                            break
                        elif command[0] == "KILL":
                            print("server is shutting down")
                            sock.close()
                            break
                        else:
                            reply = "invalid command"
                    
                    elif len(command) ==3:
                        if "Reward" in command[0]:
                            cmd, mod, amount = command
                            try:
                                amount = float(amount)
                                if cmd == "LickTriggeredReward":
                                    reward_interface.lick_triggered_reward(mod, amount)
                                    reply = f"{cmd} {mod} {amount} mLsuccessful"
                                elif cmd == "Reward":
                                    reward_interface.trigger_reward(mod, amount)
                                    reply = f"{cmd} {mod} {amount} mL successful"
                            except ValueError:
                                reply = f"invalid amount {amount} specified"
                        elif command[0] == "SetSyringeType":
                            cmd, mod, syringeType = command
                            ret = reward_interface.set_syringe_type(mod, syringeType)
                            if ret:
                                reply = f"{cmd} {mod} to {syringeType} successful"
                            else:
                                reply = f"{cmd} {mod} to {syringeType} unsuccessful. invalid syringeType"
                        elif command[0] == "SetSyringeID":
                            cmd, mod, ID = command
                            try:
                                ID = float(ID)
                                reward_interface.set_syringe_ID(mod, ID)
                                reply = f"{cmd} {mod} to {ID} successful"
                            except ValueError:
                                reply = "invalid ID {ID} specified"
                        else:
                            reply = "invalid command"
                    else:
                        reply = "invalid command"
                    
                    # Send the reply back to the client
                    conn.sendall(str.encode(reply))
                    print("reply sent")
                conn.close()
            except Exception as e:
                print(e)
                GPIO.cleanup()
                break

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--reward_config', default = 'config.yaml', help = 'path to the config file for the reward interface')
    parser.add_argument('--burst_thresh', default = 0.5,
                         help = 'time threshold in seconds on the inter lick interval for starting a new burst, consequently also the time after a lick before stopping the pump')
    parser.add_argument('--reward_thresh', default = 3, help = 'number of licks within a burst required to start the pump')
    
    args = parser.parse_args()
    reward_interface = RewardInterface(args.reward_config, args.burst_thresh, args.reward_thresh)

    start_server(reward_interface)
