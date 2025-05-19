from flwr.server.strategy import FedAvg
from utils.federation import weighted_average
from utils.logging_utils import log_metrics

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

