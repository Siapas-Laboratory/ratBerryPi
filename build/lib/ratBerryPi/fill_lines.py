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

	args = parser.parse_args()
	cl = Client(args.host, args.port, args.broadcast_port)
	cl.connect()
	
	args = {"amounts": {"module1": 6,
		                "module2": 6},
			"prime_amounts": {"module1": 1,
		                      "module2": 1},
			"res_amounts": {"pump1": 1}
    }
	for _ in range(20):
		cl.run_command("fill_lines", args)
		time.sleep(args.delay)