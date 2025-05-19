import pandas as pd
import matplotlib.pyplot as plt
import os
import glob
import seaborn as sns

# Répertoires
LOG_DIR = "../logs"
OUTPUT_DIR = "plots"

# Créer le répertoire de sortie s'il n'existe pas
os.makesdirs(OUTPUT_DIR, exist_ok = True)
