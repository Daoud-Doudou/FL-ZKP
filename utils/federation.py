import pickle
import os
import logging

logger = logging.getLogger(__name__)

def elect_next_server(state, config):
	current = state["current_server"]
	all_peers = config["all_peers"]
	idx = (all_peers.index(current) + 1) % len(all_peers)
	next_server = all_peers[idx]

	state["current_server"] = next_server

	with open("/app/shared/state.pkl", "wb") as f:
		pickle.dump(state, f)

	logger.info(f"[Election] Prochaine seveur élu: {next_server}")

def weighted_average(metrics_list):
	total_examples = sum([num_examples for num_examples, _ in metrics_list])
	avg_loss = sum([num_examples * metrics.get("loss", 0.0) for num_examples, metrics in metrics_list])/ total_examples
	avg_accuracy = sum([num_examples * metrics.get("accuracy", 0.0) for num_examples, metrics in metrics_list]) / total_examples
	return {"loss": avg_loss, "accuracy": avg_accuracy}


