#!/usr/bin/env bash
# 이미 Docker Hub에 올린 판을 dolfinid에 띄운다: bash deploy/deploy.sh v0.1.0 (devlog 007)
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="${1:?usage: deploy.sh <tag>}"
HOST="${DEPLOY_HOST:-dolfinid}"
docker manifest inspect "honestjung/shallowsea:$TAG" >/dev/null
scp -q deploy/host/docker-compose.yml "$HOST:/srv/shallowsea/docker-compose.yml"
ssh "$HOST" bash -s -- "$TAG" <<'REMOTE'
set -euo pipefail
cd /srv/shallowsea
TAG="$1"
touch .env
grep -v '^IMAGE_TAG=' .env > .env.new || true
echo "IMAGE_TAG=$TAG" >> .env.new
mv .env.new .env
docker compose pull -q
docker compose up -d
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8019/healthz </dev/null; then echo; exit 0; fi
  sleep 1
done
echo "healthz failed" >&2
exit 1
REMOTE
curl -fsS "https://shallowsea.nopeoplestime.info/healthz" && echo
