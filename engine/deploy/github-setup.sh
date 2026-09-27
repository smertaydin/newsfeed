#!/usr/bin/env bash
# Depoyu GitHub'da oluşturur ve kodu gönderir. Veri `data` dalına motor tarafından gönderilir.
set -euo pipefail
repo="${1:-newsfeed}"
cd "$(dirname "$0")/../.."
command -v git >/dev/null && command -v gh >/dev/null || { echo "Önce: sudo apt install -y git gh && gh auth login"; exit 1; }
gh auth status >/dev/null
user="$(gh api user --jq .login)"
git config --get user.name >/dev/null || git config --global user.name "$(gh api user --jq '.name // .login')"
git config --get user.email >/dev/null || git config --global user.email "$(gh api user --jq '.id').${user}@users.noreply.github.com"
gh auth setup-git
[ -d .git ] || git init -q -b main
git add -A
git diff --cached --quiet || git commit -q -m "Akış: haber motoru ve site" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$repo" --public --source . --remote origin --push \
    --description "Yerel yapay zekâ ile derlenen, sürekli güncellenen haber akışı ve RSS"
else
  git push -u origin main
fi
echo
echo "Repo:  https://github.com/$user/$repo"
echo "Veri:  https://raw.githubusercontent.com/$user/$repo/data/feed.json  (motorun ilk gönderiminden sonra)"
echo "RSS:   https://raw.githubusercontent.com/$user/$repo/data/rss.xml"
