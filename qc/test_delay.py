import nidaqmx
import threading
from ratBerryPi.client import Client
import time

do_channel = ""
host = "chamber-3"
port = 5562
broadcast = 5563
module = "module1"


########################################
client = Client(host, port, broadcast)
client.connect()

for _ in range(10):
    def ttl():
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(do_channel)
            while not start_signal.is_set():
                pass
            task.write(True)
            time.sleep(.1)
            task.write(False)

    def open_valve():
        args = {'module': module, 'open_valve': True}
        while not start_signal.is_set():
            pass
        client.run_command('toggle_valve', args)
        time.sleep(.1)
        args = {'module': module, 'open_valve': False}
        client.run_command('toggle_valve', args)


    start_signal = threading.Event()
    ttl_thread = threading.Thread(target = ttl, args = (start_signal,))
    ttl_thread.start()
    valve_thread = threading.Thread(target = open_valve, args = (start_signal,))
    valve_thread.start()
    time.sleep(1)
    start_signal.set()
    ttl_thread.join()
    valve_thread.join()




