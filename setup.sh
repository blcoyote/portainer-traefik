#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# --- Pre-flight checks ---

# Check Docker is installed
if ! command -v docker &>/dev/null; then
    error "Docker is not installed. Install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker daemon is running
if ! docker info &>/dev/null; then
    error "Docker daemon is not running. Start Docker and try again."
    exit 1
fi
info "Docker is installed and running."

# Check if ports 80 and 443 are available
for port in 80 443; do
    if lsof -iTCP:"$port" -sTCP:LISTEN -P -n &>/dev/null 2>&1; then
        warn "Port $port is already in use. Traefik needs this port — check what is bound to it."
    fi
done

# --- Create prerequisites ---

# Create proxy network
if docker network inspect proxy &>/dev/null 2>&1; then
    info "Docker network 'proxy' already exists."
else
    docker network create proxy
    info "Created Docker network 'proxy'."
fi

# Create traefik directory and acme.json
mkdir -p traefik
if [ -f traefik/acme.json ]; then
    info "traefik/acme.json already exists."
else
    touch traefik/acme.json
    chmod 600 traefik/acme.json
    info "Created traefik/acme.json with mode 600."
fi

# Create portainer data directory
mkdir -p portainer/data
info "Ensured portainer/data/ directory exists."

echo ""
info "Setup complete. Run 'docker compose up -d' to start the stack."
