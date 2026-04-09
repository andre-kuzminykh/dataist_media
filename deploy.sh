#!/bin/bash
# Deploy Dataist arXiv Pipeline to GCE server (human-1)
#
# Usage:
#   OPENAI_API_KEY=sk-... TG_BOT_TOKEN=... ./deploy.sh
#
# Or export them first:
#   export OPENAI_API_KEY=sk-...
#   export TG_BOT_TOKEN=...
#   ./deploy.sh
#
# Prerequisites:
# - gcloud CLI authenticated
# - SSH access to human-1
# - OPENAI_API_KEY and TG_BOT_TOKEN env vars set

set -euo pipefail

: "${OPENAI_API_KEY:?Set OPENAI_API_KEY env var}"
: "${TG_BOT_TOKEN:?Set TG_BOT_TOKEN env var}"

SERVER="human-1"
ZONE="europe-west1-b"
REPO_URL="https://github.com/andre-kuzminykh/dataist_media.git"
BRANCH="claude/arxiv-telegram-bot-YaDTV"
DEPLOY_DIR="/opt/dataist_media"

echo "=== Deploying Dataist arXiv Pipeline to $SERVER ==="

# Build env file contents locally (secrets never touch git)
SERVICE_ENV="OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_MODEL=gpt-4o
OPENAI_IMAGE_MODEL=dall-e-3
TELEGRAM_BOT_TOKEN=${TG_BOT_TOKEN}
TELEGRAM_CHAT_ID=
ASSET_STORAGE_TYPE=local
ASSET_STORAGE_PATH=./published
ASSET_PUBLIC_BASE_URL=http://localhost:8004/static
PROMPT_PROFILE_ID=default_ai_editorial_v1
STYLE_PROFILE_ID=cinematic_orange_violet_v1
HTML_TEMPLATE_PROFILE_ID=dataist_article_v1
REFERENCE_IMAGE_URL=
HOST=0.0.0.0
PORT=8004
LOG_LEVEL=INFO"

BOT_ENV="BOT_TOKEN=${TG_BOT_TOKEN}
BACKEND_URL=http://service:8004"

# Deploy via SSH
gcloud compute ssh "$SERVER" --zone="$ZONE" --command="
    set -e

    # Install docker compose plugin if needed
    if ! docker compose version &>/dev/null 2>&1; then
        echo 'Installing docker compose plugin...'
        sudo apt-get update -qq && sudo apt-get install -y -qq docker-compose-plugin 2>/dev/null || true
    fi

    # Clone or pull repo
    if [ -d '$DEPLOY_DIR' ]; then
        echo 'Updating existing repo...'
        cd '$DEPLOY_DIR'
        sudo git fetch origin '$BRANCH'
        sudo git checkout '$BRANCH'
        sudo git pull origin '$BRANCH'
    else
        echo 'Cloning repo...'
        sudo git clone -b '$BRANCH' '$REPO_URL' '$DEPLOY_DIR'
        cd '$DEPLOY_DIR'
    fi

    # Write .env files (secrets passed via env, not in git)
    echo '${SERVICE_ENV}' | sudo tee service/.env > /dev/null
    echo '${BOT_ENV}' | sudo tee bot/.env > /dev/null

    # Check no port conflict
    if sudo ss -tlnp | grep -q ':8004 '; then
        echo 'WARNING: Port 8004 is already in use!'
        sudo ss -tlnp | grep ':8004'
    fi

    # Build and start (safe for other containers)
    echo 'Building and starting containers...'
    sudo docker compose down --remove-orphans 2>/dev/null || true
    sudo docker compose up -d --build

    echo ''
    echo '=== Deployment complete ==='
    sudo docker compose ps
    echo ''
    echo 'Checking service health...'
    sleep 5
    curl -sf http://localhost:8004/docs > /dev/null && echo 'Service API: OK (http://localhost:8004/docs)' || echo 'Service API: still starting...'
    echo 'Bot: running (check Telegram)'
"
