#!/usr/bin/env bash
# AutoCheckBJMF 部署：GitHub main -> 影子仓 -> 运行目录 -> pm2 重启
set -e
REPO=/opt/AutoCheckBJMF_git
RUN=/opt/AutoCheckBJMF

cd "$REPO"
git fetch origin --quiet
REMOTE_HEAD=$(git rev-parse --short origin/main)
if [ -f "$RUN/DEPLOY_VERSION" ] && [ "$(cat "$RUN/DEPLOY_VERSION")" = "$REMOTE_HEAD" ]; then
    echo "已是最新版本 $REMOTE_HEAD，无需部署"
    exit 0
fi
git reset --hard origin/main --quiet
rsync -a --delete \
    --exclude "config.json" --exclude "logs/" --exclude ".venv/" --exclude "DEPLOY_VERSION" \
    "$REPO/AutoCheckBJMF/" "$RUN/"
cd "$RUN"
~/.local/bin/uv sync --python 3.11
echo "$REMOTE_HEAD" > DEPLOY_VERSION
pm2 restart AutoCheckBJMF >/dev/null
pm2 restart BJMF_TGBot 2>/dev/null || true
echo "部署完成: $REMOTE_HEAD"
