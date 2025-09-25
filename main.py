import sys
import argparse
import logging
import socket
from flpeer import FLPeer
from utils.config import load_or_init_config, load_or_init_state
from utils.federation import elect_next_server


logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":

	parser = argparse.ArgumentParser()
	parser.add_argument("--peer-id", help = "Identifiant du pair (ex: client1), facultatif si hostname=peer-id")
	args = parser.parse_args()

	config = load_or_init_config("config.yaml")
	state = load_or_init_state(config)

	peer_id = args.peer_id or socket.gethostname() 

	config["peer_id"] = peer_id
	config["is_server"] = (peer_id == state["current_server"])

	config["server"] = state["current_server"]

	if config['is_server']:
		config["host"] = '0.0.0.0'
	else:
		config["host"] = state["current_server"]


	logger.info(f"{peer_id} sera {'SERVER' if config['is_server'] else 'CLIENT'} pour cette session")

	try:
		peer = FLPeer(config)
		peer.run()
		if config['is_server']:
			elect_next_server(state, config)

	except Exception as e:
		logger.error(f"Erreur critique: {e}", exc_info = True)
		raise
