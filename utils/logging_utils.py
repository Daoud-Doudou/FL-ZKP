import os
import csv
from datetime import datetime
from typing import Optional, Dict

def create_log():
	log_dir = "/app/logs"
	try:
		os.makedirs(log_dir, exist_ok = True)
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
	except Exception as e:
		raise RuntimeError(f"Failed to create log file: {str(e)}")

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

