import pandas as pd
import matplotlib.pyplot as plt
import os
import glob
import seaborn as sns

# Répertoires
LOG_DIR = "/app/logs"
OUTPUT_DIR = "/app/logs/plots"

# Crée le dossier de sortie s'il n'existe pas
os.makedirs(OUTPUT_DIR, exist_ok=True)

def find_latest_log():
	"""Trouve le fichier de log le plus récent"""
	try:
		log_files = glob.glob(os.path.join(LOG_DIR, "server_log_*.csv"))
		if not log_files:
			raise FileNotFoundError("Aucun fichier de log trouvé dans le dossier logs/")
		log_files.sort(key=os.path.getmtime, reverse=True)
		return log_files[0]
	except Exception as e:
		print(f"Erreur lors de la recherche des logs : {e}")
	return None

def plot_metrics(log_path):
	"""Génère les graphiques à partir du fichier de log"""
	try:
		if not os.path.exists(log_path):
			raise FileNotFoundError(f"Fichier {log_path} introuvable")

		# Lecture du CSV
		df = pd.read_csv(log_path)

		if 'Phase' not in df.columns:
			raise ValueError("La colonne 'Phase' est manquante dans le fichier CSV")

		# Filtrer TRAIN et EVAL
		train_df = df[df['Phase'] == 'TRAIN'].copy()
		eval_df = df[df['Phase'] == 'EVAL'].copy()

		# Nettoyage des 'N/A'
		train_df.replace("N/A", pd.NA, inplace=True)
		eval_df.replace("N/A", pd.NA, inplace=True)

		# Conversion en numérique
		train_df['Train_Loss'] = pd.to_numeric(train_df['Train_Loss'], errors='coerce')
		train_df['Train_Accuracy'] = pd.to_numeric(train_df['Train_Accuracy'], errors='coerce')
		eval_df['Eval_Loss'] = pd.to_numeric(eval_df['Eval_Loss'], errors='coerce')
		eval_df['Eval_Accuracy'] = pd.to_numeric(eval_df['Eval_Accuracy'], errors='coerce')

		# Tracé
		plt.style.use('seaborn-v0_8')
		fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

		ax1.plot(train_df['Round'], train_df['Train_Loss'], 'b-', label="Training Loss")
		if not eval_df.empty:
			ax1.plot(eval_df['Round'], eval_df['Eval_Loss'], 'r--', label="Validation Loss")
		ax1.set_title("Évolution de la Loss")
		ax1.set_ylabel("Loss")
		ax1.legend()
		ax1.grid(True)

		ax2.plot(train_df['Round'], train_df['Train_Accuracy'], 'b-', label="Training Accuracy")
		if not eval_df.empty:
			ax2.plot(eval_df['Round'], eval_df['Eval_Accuracy'], 'r--', label="Validation Accuracy")
		ax2.set_title("Évolution de l'Accuracy")
		ax2.set_ylabel("Accuracy")
		ax2.legend()
		ax2.grid(True)

		# Nom de sortie
		base_name = os.path.basename(log_path).replace("server_log_", "metrics_").replace(".csv", ".png")
		output_path = os.path.join(OUTPUT_DIR, base_name)

		plt.tight_layout()
		plt.savefig(output_path)
		print(f"Graphiques sauvegardés dans {output_path}")
		plt.show()
		plt.close()
		return True

	except Exception as e:
		print(f"Erreur lors de la génération des graphiques : {e}")
	return False

if __name__ == "__main__":
	latest_log = find_latest_log()
	if latest_log:
		print(f"Traitement du fichier de log : {latest_log}")
		success = plot_metrics(latest_log)
		if not success:
			print("Échec de la génération des graphiques.")

