# strategy.py
from flwr.server.strategy import FedAvg
from flwr.common import parameters_to_ndarrays
from utils.federation import weighted_average
from utils.logging_utils import log_metrics
from utils.zkp_utils import export_and_maybe_prove
import numpy as np, os, json, shutil

class MyCustomFedAvg(FedAvg):
    def __init__(self, log_file=None, **kwargs):
        super().__init__(**kwargs)
        self.log_file = log_file

    def aggregate_fit(self, server_round, results, failures):
        # 1) Agrégation standard FedAvg
        parameters_aggregated, _ = super().aggregate_fit(server_round, results, failures)

        # 2) Export ZKP (2 clients + moyenne), puis (optionnel) preuve/verify
        try:
            save_dir = f"/app/shared/zkp/round{server_round}"
            if os.path.exists(save_dir):
                shutil.rmtree(save_dir)
            os.makedirs(save_dir, exist_ok=True)

            if len(results) >= 2:  # si <2, on skip l'export proprement
                # Tri stable par client_id si dispo
                def _key(res):
                    m = res[1].metrics or {}
                    return m.get("client_id", "zz")
                sorted_results = sorted(results, key=_key)[:2]

                # clients.json
                clients_payload = []
                for _, fit_res in sorted_results:
                    w_nd = parameters_to_ndarrays(fit_res.parameters)
                    flat = np.concatenate([w.ravel() for w in w_nd]).astype(float).tolist()
                    clients_payload.append({
                        "client_id": (fit_res.metrics or {}).get("client_id", "unknown"),
                        "num_examples": int(fit_res.num_examples),
                        "flat_weights": flat,
                    })
                with open(os.path.join(save_dir, "clients.json"), "w") as f:
                    json.dump({"clients": clients_payload}, f, indent=2)

                # avg.json
                if parameters_aggregated is not None:
                    w_avg_nd = parameters_to_ndarrays(parameters_aggregated)
                    w_avg_flat = np.concatenate([w.ravel() for w in w_avg_nd]).astype(float).tolist()
                    with open(os.path.join(save_dir, "avg.json"), "w") as f:
                        json.dump({"avg": w_avg_flat}, f, indent=2)

                #  Appel central : export des chunks (+ prove/verify si ZKP_AUTOPROVE=1)
                export_and_maybe_prove(save_dir)

        except Exception as e:
            print(f"[ZKP] Erreur sauvegarde/export/prove round {server_round}: {e}")

        # 3) Agrégation de métriques
        train_metrics = {}
        try:
            if results and not failures:
                metrics_list = [(r.num_examples, r.metrics or {}) for _, r in results]
                total = sum(n for n, _ in metrics_list) or 0
                if total > 0:
                    keys = set().union(*(m.keys() for _, m in metrics_list)) if metrics_list else set()
                    for k in keys:
                        vals = [(n, m[k]) for n, m in metrics_list if k in m and isinstance(m[k], (int, float))]
                        if vals:
                            s_num = sum(n * v for n, v in vals)
                            s_den = sum(n for n, _ in vals)
                            if s_den > 0:
                                train_metrics[k] = s_num / s_den
                log_metrics(self.log_file, server_round, train_metrics or None, None)
        except Exception as e:
            print(f"[METRICS] Erreur agrégation métriques round {server_round}: {e}")
            train_metrics = {}

        # 4) Retour Flower
        return parameters_aggregated, train_metrics


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