import logging
import torch
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
import flwr as fl
from flwr.server import ServerConfig
from model import Net
from strategy import MyCustomFedAvg
from client import FLClient
from utils.logging_utils import create_log
from typing import Dict, Tuple
import time
import socket

logger = logging.getLogger(__name__)

def wait_for_server(host, port, timeout = 30):
	""" Attendre que le serveur gRRC soit disponible avant de lancer le client"""
	logger.info(f"Attente de connexion au serveur {host}:{port}...")
	start = time.time()
	while time.time() - start < timeout:
		try:
			with socket.create_connection((host, port), timeout=2):
				logger.info("serveur disponible")
				return
		except OSError:
			time.sleep(1)
	raise RuntimeError("Impossible de se connecter au serveur flower.")



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
		wait_for_server(self.config["host"], self.config["port"])
		fl.client.start_numpy_client(
			server_address = f"{self.config['host']}:{self.config['port']}",
			client = FLClient(self.model, self.train_loader, self.val_loader, self.device )
		)

