from ratBerryPi.interface import RewardInterface
import time

def run_test(reward_interface, module, amount, delay = 5, n_pulses = 20):
	for _ in range(n_pulses):
		reward_interface.trigger_reward(module, amount, sync = True)
		time.sleep(delay)



if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	
	parser.add_argument("--module", required = True)
	parser.add_argument("--amount", required = True,  type = float)
	parser.add_argument("--delay", default = 5., type = float)
	parser.add_argument("--n_pulses", default = 20, type = int)

	args = parser.parse_args()
	r = RewardInterface()
	run_test(r, args.module, args.amount, args.delay, args.n_pulses)