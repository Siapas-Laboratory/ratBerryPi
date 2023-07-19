import sys
sys.path.append('../')
from client import connect_client
import time
if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("--host", default = "192.168.0.246")
	parser.add_argument("--port", default = "5560")
	args = parser.parse_args()
	cl = Client(args.host, args.port)
	if cl is not None:
		for _ in range(20):
			cl.trigger_reward("module1", 0.005)
			time.sleep(5)