#!/usr/bin/env bash
# Motoru kullanıcı servisi olarak kurar; oturum kapalıyken de çalışır.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.config/systemd/user
sed "s#%h/NewsFeed#$(cd "$here/../.." && pwd)#" "$here/akis-engine.service" > ~/.config/systemd/user/akis-engine.service
systemctl --user daemon-reload
systemctl --user enable --now akis-engine.service
loginctl enable-linger "$USER" || echo "Uyarı: oturum kapalıyken çalışması için 'sudo loginctl enable-linger $USER' çalıştırın."
echo "Kuruldu. Loglar: journalctl --user -u akis-engine -f"
