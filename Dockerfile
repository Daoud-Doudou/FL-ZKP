

# ---------- STAGE 1 : build de circom ----------
    FROM rust:1.80-bullseye AS circom-builder

    # Outils de build
    RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential ca-certificates pkg-config libssl-dev \
     && rm -rf /var/lib/apt/lists/*
    
    # Récupérer et compiler circom
    WORKDIR /src
    RUN git clone --depth 1 https://github.com/iden3/circom.git
    WORKDIR /src/circom
    # Compile en release
    RUN cargo build --release
    # Le binaire est dans target/release/circom -> on l'extrait
    RUN install -Dm755 target/release/circom /out/circom
    
    # ---------- STAGE 2 : image finale ----------
    # Ton image de base Python (on conserve exactement ta version)
    FROM python:3.9-slim-bullseye
    
    # 1) Outils système + Node.js + npm (pour snarkjs)
    RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
     && rm -rf /var/lib/apt/lists/*
    
    # Installer Node.js LTS (18.x) depuis NodeSource pour éviter une version trop vieille
    RUN set -eux; \
        ARCH="$(dpkg --print-architecture)"; \
        case "$ARCH" in \
          amd64)  NODE_ARCH="x64" ;; \
          arm64)  NODE_ARCH="arm64" ;; \
          *) echo "Arch non supportée: $ARCH"; exit 1 ;; \
        esac; \
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
     && apt-get update && apt-get install -y --no-install-recommends nodejs \
     && rm -rf /var/lib/apt/lists/*
    
    # Installer snarkjs globalement
    RUN npm install -g snarkjs
    
    # 2) Ajouter l'utilisateur non-root (comme tu faisais)
    RUN useradd -u 1000 -ms /bin/bash fluser
    
    # 3) Dossiers applicatifs et droits
    RUN mkdir -p /app/logs /app/shared /app/certificates \
     && chown -R fluser:fluser /app \
     && chmod -R 750 /app
    
    # 4) Copier le binaire circom compilé dans /usr/local/bin
    COPY --from=circom-builder /out/circom /usr/local/bin/circom
    
    # 5) Python deps (on garde exactement tes étapes)
    WORKDIR /app
    COPY --chown=fluser requirements.txt .
    
    # PyTorch CPU-only avant le reste
    RUN pip install --no-cache-dir \
      https://download.pytorch.org/whl/cpu/torch-2.1.0%2Bcpu-cp39-cp39-linux_x86_64.whl
    
    # Autres dépendances Python
    RUN pip install --no-cache-dir -r requirements.txt
    
    # 6) Copier ton code
    COPY --chown=fluser config.yaml .
    COPY --chown=fluser *.py .
    COPY --chown=fluser utils/ ./utils
    COPY --chown=fluser zkp/ ./zkp

    
    USER fluser
    
    # 7) Passer à l'utilisateur non-root
    USER fluser
    
    # 8) Commande par défaut
    ENTRYPOINT ["python", "main.py"]