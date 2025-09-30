# ---------- STAGE 1 : build de circom ----------
  FROM rust:1.80-bullseye AS circom-builder
  RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential ca-certificates pkg-config libssl-dev \
   && rm -rf /var/lib/apt/lists/*
  WORKDIR /src
  RUN git clone --depth 1 https://github.com/iden3/circom.git
  WORKDIR /src/circom
  RUN cargo build --release
  RUN install -Dm755 target/release/circom /out/circom
  
  # ---------- STAGE 2 : image finale ----------
  FROM python:3.9-slim-bullseye
  
  # 1) Outils système + Node.js + npm
  RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg \
   && rm -rf /var/lib/apt/lists/*
  
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
  
  # Installer snarkjs globalement (optionnel, on l’a aussi en deps locale)
  RUN npm install -g snarkjs
  
  # 2) Utilisateur non-root
  RUN useradd -u 1000 -ms /bin/bash fluser
  
  # 3) Dossiers applicatifs et droits
  RUN mkdir -p /app/logs /app/shared /app/certificates \
   && chown -R fluser:fluser /app \
   && chmod -R 750 /app
  
  # 4) Copier circom
  COPY --from=circom-builder /out/circom /usr/local/bin/circom
  
  # 5) Python deps
  WORKDIR /app
  COPY --chown=fluser requirements.txt .
  RUN pip install --no-cache-dir \
    https://download.pytorch.org/whl/cpu/torch-2.1.0%2Bcpu-cp39-cp39-linux_x86_64.whl
  RUN pip install --no-cache-dir -r requirements.txt
  
  # 🔹 6) Installer les deps Node DU PROJET (circomlibjs, ffjavascript, snarkjs local)
  #    -> on copie d'abord les manifests pour profiter du cache Docker
  COPY package*.json ./
  RUN npm install --omit=dev
  
  # 7) Copier ton code après (pour ne pas casser le cache npm à chaque modif)
  COPY --chown=fluser config.yaml .
  COPY --chown=fluser *.py .
  COPY --chown=fluser utils/ ./utils
  COPY --chown=fluser zkp/ ./zkp
  
  # 8) Utilisateur non-root
  USER fluser
  
  # 9) Entrypoint
  ENTRYPOINT ["python", "main.py"]
  