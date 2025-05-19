import flwr as fl
import torch
import torch.nn as nn
import torch.optim as optim
import logging
from model import Net
from torchvision import transforms, datasets
from torch.utils.data import DataLoader, Subset
from flwr.server import ServerConfig
from flwr.server.strategy import FedAvg
from typing import Dict, Tuple, Optional
import yaml
from pathlib import Path
import pickle
import argparse
import os
from datetime import datetime
import csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_log():
	os.makedirs("logs", exist_ok = True)
	log_file = f"logs/server_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

	with open(log_file, mode = "w", newline= "", encoding = "utf-8") as f:
		writer = csv.writer(f)
		writer.writerow([
			"Round",
			"Train_Loss",
			"Train_Accuracy",
			"Eval_Loss",
			"Eval_Accuracy",
			"Phase"
		])
	return log_file


def load_or_init_config(config_path: str)-> Dict:
	with open(config_path) as f:
		return yaml.safe_load(f)

def load_or_init_state(config_path)-> Dict:
	state_file = Path("state.pkl")
	if state_file.exists():
		with open (state_file, "rb") as f:
			return pickle.load(f)
	else:
		initial_server = config["all_peers"][0]
		state = {
			"current_server" : initial_server
		}
		with open(state_file, "wb") as f:
			pickle.dump(state, f)
		return state

def elect_next_server(state, config):
	current = state["current_server"]
	all_peers = config["all_peers"]
	idx = (all_peers.index(current) + 1) % len(all_peers)
	next_server = all_peers[idx]

	state["current_server"] = next_server

	with open("state.pkl", "wb") as f:
		pickle.dump(state, f)

	logger.info(f"[Election] Prochaine seveur élu: {next_server}")

def weighted_average(metrics_list):
	total_examples = sum([num_examples for num_examples, _ in metrics_list])
	avg_loss = sum([num_examples * metrics.get("loss", 0.0) for num_examples, metrics in metrics_list])/ total_examples
	avg_accuracy = sum([num_examples * metrics.get("accuracy", 0.0) for num_examples, metrics in metrics_list]) / total_examples
	return {"loss": avg_loss, "accuracy": avg_accuracy}


def log_metrics(log_file:str, server_round:int, train_metrics:Optional[Dict], eval_metrics:Optional[Dict]):
	def fmt(val):
		return f"{val:4f}" if isinstance(val, (float,int)) else "N/A"

	write_header = not os.path.exists(log_file)

	with open(log_file, mode = "a", newline = "") as f:
		writer = csv.writer(f)

		if write_header:
			writer.writerow(["Round", "Train_Loss", "Train_Accuracy", "Eval_Loss", "Eval_Accuracy", "Phase"])

		if train_metrics:
			writer.writerow([
				server_round,
				fmt(train_metrics.get("loss")),
				fmt(train_metrics.get("accuracy")),
				"N/A",
				"N/A",
				"TRAIN"
			])
		if eval_metrics:
			writer.writerow([
				server_round,
				"N/A",
				"N/A",
				fmt(eval_metrics.get("loss")),
				fmt(eval_metrics.get("accuracy")),
				"EVAL"
			])


class MyCustomFedAvg(FedAvg):
	def __init__(self, log_file = None, **kwargs):
		super().__init__(**kwargs)
		self.log_file = log_file

	def aggregate_fit(self, server_round, results, failures):
		parameters_aggregated, _ = super().aggregate_fit(server_round, results, failures)
		if results and not failures:
			metrics_list = [
				(r.num_examples, r.metrics)
				for _, r in results if r.metrics is not None
			]
			train_metrics = weighted_average(metrics_list)
			log_metrics(self.log_file, server_round, train_metrics, None)
			return parameters_aggregated, train_metrics
		return parameters_aggregated, {}

	def aggregate_evaluate(self, server_round, results, failures):
		aggregated_loss, _ = super().aggregate_evaluate(server_round, results, failures)
		if results and not failures:
			metrics_list = [
				(r.num_examples, r.metrics)
				for _, r in results if r.metrics is not None 
			]
			eval_metrics = weighted_average(metrics_list)
			log_metrics(self.log_file, server_round, None, eval_metrics)
			return aggregated_loss, eval_metrics
		return aggregated_loss, {}


class FLPeer:
	def __init__(self, config: Dict):
		self.config = config

		if self.config['device'] == 'auto':
			self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
		else:
			self.device = torch.device(self.config['device'])
		self.config['device'] = str(self.device)

		self.model = Net().to(self.config['device'])
		self.is_server = self.config['is_server']

		# chargement des données
		self.train_loader, self.val_loader = self.load_data()

		logger.info(f"Pair {self.config['peer_id']} initailisé en tant que {'SERVER' if self.is_server else 'CLIENT'}")

	def load_data(self) -> Tuple[DataLoader, DataLoader]:
		""" Charge les données MNIST avec un sous ensemble différent pour chaque pair """
		transform = transforms.Compose([
			transforms.ToTensor(),
			transforms.Normalize((0.1307),(0.3081))
		])

		full_train = datasets.MNIST(
			"./data",
			train = True,
			download = True,
			transform = transform
		)

		test_data = datasets.MNIST(
			"./data",
			train = False,
			transform = transform
		)

		# Répartition des données entre clients
		peer_idx = self.config['all_peers'].index(self.config['peer_id'])
		n_peers = len(self.config['all_peers'])
		subset_size = len(full_train) // n_peers
		indices = range(peer_idx * subset_size, (peer_idx +1) * subset_size)

		train_subset = Subset(full_train, indices)
		val_size = int(0.2 * len(train_subset))
		train_size = len(train_subset) - val_size


		train_set, val_set = torch.utils.data.random_split(
			train_subset,
			[train_size, val_size]
		)

		return (
			DataLoader(train_set, batch_size = 32, shuffle = True),
			DataLoader(val_set, batch_size = 32)
		)

	def run(self):
		if self.is_server:
			log_file = create_log()
			self.run_server(log_file)
		else:
			self.run_client()

	def run_server(self, log_file):
		strategy = MyCustomFedAvg(
			log_file = log_file,
			min_fit_clients = self.config['min_clients'],
			min_evaluate_clients = self.config['min_clients'],
			min_available_clients = self.config['min_clients']
		)

		server_config = ServerConfig(num_rounds = self.config['num_rounds'])

		fl.server.start_server(
			server_address = f"{self.config['host']}:{self.config['port']}",
			config = server_config,
			strategy = strategy
		)

	def run_client(self):
		fl.client.start_numpy_client(
			server_address = f"{self.config['host']}:{self.config['port']}",
			client = FLClient(self.model, self.train_loader, self.val_loader, self.device )
		)

class FLClient(fl.client.NumPyClient):
	def __init__(self, model, train_loader, val_loader, device):
		self.model = model
		self.train_loader = train_loader
		self.val_loader = val_loader
		self.device = device
		self.criterion = nn.CrossEntropyLoss()

	# récupère les poids de modèle local
	def get_parameters(self, config):
		return [val.cpu().numpy() for val in self.model.state_dict().values()]

	def set_parameters(self, parameters):
		params_dict = zip(self.model.state_dict().keys(), parameters)
		state_dict = {k: torch.tensor(v).to(self.device)  for k, v in params_dict}
		self.model.load_state_dict(state_dict, strict = True)

	def fit(self, parameters, config):
		self.set_parameters(parameters)

		optimizer = optim.SGD(self.model.parameters(), lr = config.get("lr", 0.01))

		self.model.train()

		total_loss = 0
		correct = 0
		total = 0

		for epoch in range(config.get("epochs", 1)):
			for batch_idx, (data, target) in enumerate(self.train_loader):
				data, target = data.to(self.device), target.to(self.device)
				optimizer.zero_grad()
				output = self.model(data)
				loss = self.criterion(output, target)
				loss.backward()
				optimizer.step()

				# calcul les metrics
				total_loss += loss.item() * data.size(0)
				preds = output.argmax(dim = 1)
				correct += (target == preds).sum().item()
				total += target.size(0)

		loss = total_loss / total
		accuracy = correct / total

		return (self.get_parameters({}), len(self.train_loader.dataset), {"loss": loss, "accuracy": accuracy})

	def evaluate(self, parameters, config):
		self.set_parameters(parameters)

		self.model.eval()
		total_loss = 0
		correct = 0
		total = 0

		with torch.no_grad():
			for data, target in self.val_loader:
				data, target = data.to(self.device), target.to(self.device)
				output = self.model(data)
				total_loss += self.criterion(output, target).item()
				pred = output.argmax(dim = 1)
				correct += (target == pred).sum().item()
				total += target.size(0)

			accuracy = correct / total
			avg_loss = total_loss / total

		return (float(avg_loss), total, {"loss": avg_loss, "accuracy" : accuracy})

if __name__ == "__main__":

	parser = argparse.ArgumentParser()
	parser.add_argument("--peer-id", required = True, help = "Identifiant du pair (ex: client1)")
	args = parser.parse_args()

	config = load_or_init_config("config.yaml")
	state = load_or_init_state(config)

	config["peer_id"] = args.peer_id
	config["is_server"] = (args.peer_id == state["current_server"])

	logger.info(f"{args.peer_id} sera {'SERVER' if config['is_server'] else 'CLIENT'} pour cette session")

	try:
		peer = FLPeer(config)
		peer.run()
		if config['is_server']:
			elect_next_server(state, config)

	except Exception as e:
		logger.error(f"Erreur critique: {e}", exc_info = True)
		raise
