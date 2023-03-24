import socket
from reward import RewardInterface, RewardModule

host = 'localhost'
port = 5560

def start_server(reward_interface):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            print('binding')
            sock.bind((host, port))
        except socket.error as msg:
            print(msg)
        
        while True:
            try:
                sock.listen()
                conn, _ =  sock.accept()
                print('waiting...')
                while True:
                    # Receive the data
                    # should there be a timeout on this?
                    data = conn.recv(1024) # receive the data
                    command = data.decode('utf-8')
                    command = command.split(' ')

                    if len(command)==1:
                        if command[0] == "EXIT":
                            print("Our client has left us :(")
                            break
                        elif command[0] == "KILL":
                            print("Our server is shutting down.")
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
                                    cmd, mod, amount = command
                                    reward_interface.lick_triggered_reward(mod, amount)
                                    reply = f"{cmd} {mod} {amount} mLsuccessful"
                                elif cmd == "Reward":
                                    cmd, mod, amount = command
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
                    print("Data has been sent!")
                conn.close()
            except:
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
