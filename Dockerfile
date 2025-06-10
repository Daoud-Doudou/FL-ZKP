# choix de l'image de base 
FROM python:3.9.5-slim

# Créer un utilisateur non-root pour éviter de lancer le projet en root
RUN useradd -u 1000 -ms /bin/bash fluser

# Créer le dossier partagé avec les bons droits
RUN mkdir -p /app/logs /app/shared && chown -R fluser:fluser /app && chmod -R 750 /app/logs

# Configuration de l'environement
WORKDIR /app
COPY --chown=fluser requirements.txt .

# Install les dépendances listées dans requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copie des fichiers
COPY --chown=fluser . .

# Passer à l'utilisateur
USER fluser

# Spécifie la commande par défault
ENTRYPOINT ["python", "main.py"]  
