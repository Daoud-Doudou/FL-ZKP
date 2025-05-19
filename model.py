import torch
import torch.nn as nn
import torch.nn.functional as F

class Net(nn.Module):
	def __init__(self):
		super(Net, self).__init__()
		self.fc1 = nn.Linear(28 * 28, 512)
		self.fc2 = nn.Linear(512, 256)
		self.fc3 = nn.Linear(256, 10)

	def forward(self, x):
		x = x.view(-1, 28 * 28)
		x = F.relu(self.fc1(x))
		x = F.relu(self.fc2(x))
		x = self.fc3(x)
		return x

if __name__ == "__main__":
	model = Net()

	input = torch.rand(1, 1, 28, 28)
	output = model(input)
