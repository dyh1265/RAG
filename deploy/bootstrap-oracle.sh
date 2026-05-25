#!/usr/bin/env bash
# Bootstrap DocuMind demo on Ubuntu 22.04/24.04 (Oracle Cloud ARM or amd64).
# Run as a normal user with sudo:
#   curl -fsSL <raw-url>/deploy/bootstrap-oracle.sh | bash
# Or from a cloned repo:
#   bash deploy/bootstrap-oracle.sh
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/RAG}"
PROFILE="--profile production"

log() { printf '==> %s\n' "$*"; }

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required." >&2
  exit 1
fi

log "Installing Docker (if missing)..."
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y ca-certificates curl git
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
  log "Docker installed. If 'docker' fails, log out/in or run: newgrp docker"
fi

log "Adding 4G swap (helps first PyTorch/model build on small VMs)..."
if ! swapon --show | grep -q '/swapfile'; then
  sudo fallocate -l 4G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  if ! grep -q '/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  fi
fi

if [[ ! -d "$REPO_DIR/.git" ]]; then
  log "Clone the repo into $REPO_DIR first, then re-run this script."
  exit 1
fi

cd "$REPO_DIR"

if [[ ! -f .env ]]; then
  cp deploy/.env.demo.example .env
  log "Created .env from deploy/.env.demo.example — edit OPENAI_API_KEY before going live."
fi

if ! grep -q '^OPENAI_API_KEY=sk-' .env 2>/dev/null; then
  log "WARNING: Set OPENAI_API_KEY in $REPO_DIR/.env"
fi

log "Building and starting demo stack (first run can take 15-30 min)..."
cd docker
docker compose $PROFILE up -d --build qdrant redis rag-api ingest-worker documind-web

log "Waiting for API readiness..."
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8002/ready >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

PUBLIC_IP="$(curl -sf ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
log "Demo UI:  http://${PUBLIC_IP}/"
log "API (local only): http://127.0.0.1:8002/health"
log "Open Oracle ingress port 80 if the UI is not reachable from your browser."
