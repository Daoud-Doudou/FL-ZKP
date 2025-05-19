import flwr as fl
import torch
import torch.nn as nn
import torch.optim as optim

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

