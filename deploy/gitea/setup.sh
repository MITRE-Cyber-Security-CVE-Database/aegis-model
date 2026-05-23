#!/usr/bin/env bash
# Autonomous Gitea bootstrap for AEGIS.
# Spins up Gitea, creates an admin user, mints an API token, creates the aegis-model repo,
# adds it as a git remote, and pushes the entire history.
#
# Usage:  bash setup.sh [admin-password]
set -euo pipefail

PW="${1:-${GITEA_ADMIN_PW:-aegis-$(openssl rand -hex 8)}}"
USER="aegis"
EMAIL="aegis@localhost"
HOST="http://localhost:3030"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "[*] Working dir: $REPO_DIR"
cd "$(dirname "$0")"

echo "[*] Starting Gitea + runner..."
docker compose up -d gitea

echo "[*] Waiting for Gitea API to come up..."
for i in $(seq 1 60); do
  if curl -fsS "$HOST/api/v1/version" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "$HOST/api/v1/version" >/dev/null || { echo "ERR: gitea not responding"; exit 1; }

echo "[*] Creating admin user '$USER'..."
docker exec -u git aegis-gitea gitea admin user create \
  --username "$USER" --password "$PW" --email "$EMAIL" --admin --must-change-password=false \
  2>/dev/null || echo "  (user may already exist)"

echo "[*] Minting API token..."
TOKEN=$(curl -fsS -u "$USER:$PW" -X POST "$HOST/api/v1/users/$USER/tokens" \
  -H 'Content-Type: application/json' \
  -d '{"name":"autonomous-'"$(date +%s)"'","scopes":["write:repository","write:user","write:admin"]}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["sha1"])')

if [ -z "$TOKEN" ]; then
  echo "ERR: token mint failed"; exit 1
fi
echo "  Token: ${TOKEN:0:8}... (saved to .gitea-token)"
echo "$TOKEN" > "$REPO_DIR/.gitea-token"
chmod 600 "$REPO_DIR/.gitea-token"

echo "[*] Creating repo '$USER/aegis-model'..."
curl -fsS -X POST "$HOST/api/v1/user/repos" \
  -H "Authorization: token $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"aegis-model","description":"AEGIS military-grade cyber AI","private":false,"auto_init":false}' \
  >/dev/null 2>&1 || echo "  (repo may already exist)"

echo "[*] Configuring git remote in $REPO_DIR..."
cd "$REPO_DIR"
REMOTE_URL="http://$USER:$TOKEN@localhost:3030/$USER/aegis-model.git"
if git remote get-url gitea >/dev/null 2>&1; then
  git remote set-url gitea "$REMOTE_URL"
else
  git remote add gitea "$REMOTE_URL"
fi

echo "[*] Pushing to gitea..."
git push -u gitea main

echo
echo "==== DONE ===="
echo "  Gitea:  $HOST"
echo "  Repo:   $HOST/$USER/aegis-model"
echo "  User:   $USER"
echo "  Pass:   $PW"
echo "  Token:  ${TOKEN:0:8}... (in $REPO_DIR/.gitea-token)"
echo
echo "Next steps for autonomous CI:"
echo "  TOKEN=\$(docker exec aegis-gitea gitea actions generate-runner-token)"
echo "  GITEA_RUNNER_TOKEN=\$TOKEN docker compose up -d runner"
