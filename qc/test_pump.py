import sys
sys.path.append('../')
from client import *
import time
if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("--host", default = "192.168.0.246")
	parser.add_argument("--port", default = 5562, type = int)
	parser.add_argument("--broadcast_port", default = 5563, type = int)
	parser.add_argument("--amount", required = True,  type = float)
	parser.add_argument("--delay", default = 5., type = float)

	args = parser.parse_args()
	cl = Client(args.host, args.port, args.broadcast_port)
	cl.connect()
	# cl.run_command("toggle_auto_fill", {'on': True})
	
	cl_args = {"module": "module1",
	 		"amount": args.amount,
			"sync": True}
	for _ in range(20):
		cl.run_command("trigger_reward", cl_args)
		time.sleep(args.delay)