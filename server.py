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
                        if command == 'EXIT':
                            print("Our client has left us :(")
                            break
                        elif command == 'KILL':
                            print("Our server is shutting down.")
                            sock.close()
                            break
                        else:
                            reply = 'invalid command'
                    
                    elif len(command) ==3:
                        if command == 'LickTriggeredReward':
                            command, mod, amount = command
                            reward_interface.lick_triggered_reward(mod, amount)
                            reply = f"{command} {mod} {amount} mLsuccessful"
                        if command == 'Reward':
                            command, mod, amount = command
                            reward_interface.trigger_reward(mod, amount)
                            reply = f"{command} {mod} {amount} mL successful"
                        if command == 'SetSyringeType':
                            command, mod, syringeType = command
                            reward_interface.set_syringe_type(mod, syringeType)
                            reply = f"{command} {mod} to {syringeType} successful"
                        elif command == 'SetSyringeID':
                            command, mod, ID = command
                            reward_interface.set_syringe_ID(mod, ID)
                            reply = f"{command} {mod} to {ID} successful"
                        else:
                            reply = 'invalid command'
                    else:
                        reply = 'invalid command'
                    
                    # Send the reply back to the client
                    conn.sendall(str.encode(reply))
                    print("Data has been sent!")
                conn.close()
            except:
                break

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('reward_config', default = 'config.yaml', help = 'path to the config file for the reward interface')
    parser.add_argument('--burst_thresh', default = 0.5,
                         help = 'time threshold in seconds on the inter lick interval for starting a new burst, consequently also the time after a lick before stopping the pump')
    parser.add_argument('--reward_thresh', default = 3, help = 'number of licks within a burst required to start the pump')
    
    args = parser.parse_args()
    reward_interface = RewardInterface(args.reward_config, args.burst_thresh, args.reward_thresh)

    start_server(reward_interface)
