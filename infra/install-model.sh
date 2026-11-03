#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
mkdir -p /var/lib/schema-model
exec >>/var/log/schema-model-install.log 2>&1
apt-get update -qq
apt-get install -y curl ca-certificates python3 zstd
if ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh -o /tmp/schema-ollama-install.sh
  sh /tmp/schema-ollama-install.sh
fi
mkdir -p /var/lib/schema-model/models
chown -R ollama:ollama /var/lib/schema-model/models
cat >/etc/systemd/system/ollama.service <<'EOF'
[Unit]
Description=Schema matching model server
After=network-online.target
[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
WorkingDirectory=/usr/share/ollama
Restart=always
RestartSec=3
Environment="OLLAMA_MODELS=/var/lib/schema-model/models"
Environment="OLLAMA_NO_CLOUD=1"
[Install]
WantedBy=multi-user.target
EOF
mkdir -p /etc/systemd/system/ollama.service.d
cat >/etc/systemd/system/ollama.service.d/local-only.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_NUM_PARALLEL=1"
EOF
systemctl daemon-reload
systemctl enable ollama
systemctl restart ollama
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then break; fi
  sleep 2
done
curl -fsS --max-time 900 http://127.0.0.1:11434/api/pull -d '{"model":"qwen3:4b","stream":false}'
curl -fsS http://127.0.0.1:11434/api/tags >/var/lib/schema-model/ready.json
touch /var/lib/schema-model/ready
