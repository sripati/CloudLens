#!/bin/bash
# Deploy (or update) CloudLens on an EC2 host with Docker Compose.
#
# Usage (from the project root on your laptop):
#   EC2_HOST=13.233.10.20 SSH_KEY=~/.ssh/my-key.pem ./deploy/aws/deploy.sh
#
# What it does: rsyncs the project (excluding node_modules, .git, local .env), uploads
# .env.staging as .env if present, then builds and starts the stack on the server.
set -euo pipefail

EC2_HOST=${EC2_HOST:?set EC2_HOST to the instance public IP or DNS}
SSH_KEY=${SSH_KEY:?set SSH_KEY to your .pem file}
EC2_USER=${EC2_USER:-ec2-user}
REMOTE_DIR=${REMOTE_DIR:-/opt/cloudlens}
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new $EC2_USER@$EC2_HOST"

cd "$(dirname "$0")/../.."

echo "==> Syncing project to $EC2_HOST:$REMOTE_DIR"
rsync -az --delete -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new" \
  --exclude node_modules --exclude .git --exclude frontend/dist --exclude .env --exclude 'secrets/*.json' \
  --exclude __pycache__ --exclude docs/report --exclude backups \
  ./ "$EC2_USER@$EC2_HOST:$REMOTE_DIR/"

if [ -f .env.staging ]; then
  echo "==> Uploading .env.staging as .env"
  scp -i "$SSH_KEY" .env.staging "$EC2_USER@$EC2_HOST:$REMOTE_DIR/.env"
fi
if [ -f secrets/gcp-key.json ]; then
  scp -i "$SSH_KEY" secrets/gcp-key.json "$EC2_USER@$EC2_HOST:$REMOTE_DIR/secrets/gcp-key.json"
fi

echo "==> Building and starting containers"
$SSH "cd $REMOTE_DIR && test -f .env || { echo 'Missing .env on server (create .env.staging locally)'; exit 1; } \
  && docker compose up -d --build --remove-orphans && docker image prune -f >/dev/null && docker compose ps"

echo "==> Waiting for health check"
for i in $(seq 1 30); do
  if $SSH "curl -fsS http://localhost/health" >/dev/null 2>&1 || $SSH "curl -fsS http://localhost:\$(grep -E '^HTTP_PORT=' $REMOTE_DIR/.env | cut -d= -f2)/health" >/dev/null 2>&1; then
    echo "Healthy. Open http://$EC2_HOST/"
    exit 0
  fi
  sleep 5
done
echo "Health check did not pass yet; inspect with: $SSH 'cd $REMOTE_DIR && docker compose logs --tail=100 backend'"
exit 1
