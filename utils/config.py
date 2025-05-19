import yaml
import pickle
from pathlib import Path
from typing import Dict
import os

def load_or_init_config(config_path: str)-> Dict:
	with open(config_path) as f:
		return yaml.safe_load(f)

def load_or_init_state(config: Dict)-> Dict:
	state_file = Path("/app/shared/state.pkl")
	try:
		if state_file.exists():
			with open (state_file, "rb") as f:
				return pickle.load(f)
		else:
			state_file.parent.mkdir(parents = True, exist_ok = True)
			initial_server = config["all_peers"][0]
			state = {
				"current_server" : initial_server
			}
			with open(state_file, "wb") as f:
				pickle.dump(state, f)
			return state
	except PermissionError:
		raise RuntimeError("Permission denied. Verify volume permissions.")
