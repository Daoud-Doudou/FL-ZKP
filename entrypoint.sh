#!/bin/bash

# Crée le dossier s’il n’existe pas
mkdir -p /home/fluser/app/shared

# Donne les bons droits à fluser
chown -R fluser:fluser /home/fluser/app/shared || true

# Lancer la commande finale passée (comme ["python", "main.py", "--peer-id", "client1"])
exec "$@"
