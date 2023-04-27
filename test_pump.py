from client import connect_client
import time
if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("--host", default = "192.168.0.246")
	parser.add_argument("--port", default = "5560")
	args = parser.parse_args()
	cl = connect_client(args.host, args.port)
	if cl is not None:
		for _ in range(20):
			cl.sendall("Reward module2 0.01".encode("utf-8"))
			time.sleep(2.5)
