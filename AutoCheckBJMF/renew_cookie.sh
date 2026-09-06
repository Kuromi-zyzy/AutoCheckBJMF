#!/usr/bin/env bash
# Cookie 一键续期：拉起 Windows 扫码 → 合并新 cookie → 上传服务器 → 重启验证
# 用法：bash renew_cookie.sh （弹出浏览器后用微信扫码，120 秒内完成）
set -e

PROJ="$(cd "$(dirname "$0")" && pwd)"
WIN_PROJ='D:\Tools\ClassMagicSign\AutoCheckBJMF'
WIN_CFG='/mnt/d/Tools/ClassMagicSign/AutoCheckBJMF/config.json'
SERVER='tang@20.89.98.255'
KEY="$HOME/.ssh/zhaoyang.pem"

started=$(date +%s)

echo "[1/4] 拉起 Windows 扫码窗口，请在弹出的浏览器里用微信扫码（120 秒超时）..."
/mnt/c/Windows/System32/cmd.exe /c "chcp 65001 >nul & cd /d $WIN_PROJ && .venv\Scripts\python.exe src\update_cookie.py" 2>&1 | grep -aE "抓取成功|已替换|已追加|已保存|X |ERROR" || true

if [ "$(stat -c %Y "$WIN_CFG")" -lt "$started" ]; then
    echo "✗ 抓取未成功（Windows config.json 没有更新），请重跑本脚本再扫一次"
    exit 1
fi

echo "[2/4] 合并新 cookie 到本地配置..."
python3 - << 'PYEOF'
import json
win = json.load(open('/mnt/d/Tools/ClassMagicSign/AutoCheckBJMF/config.json'))
local = json.load(open('/home/tang/projects/classmagic-sign/AutoCheckBJMF/config.json'))
local['cookies'] = win['cookies']
with open('/home/tang/projects/classmagic-sign/AutoCheckBJMF/config.json', 'w') as f:
    json.dump(local, f, indent=4, ensure_ascii=False)
print(f"  已合并 {len(local['cookies'])} 个账号 cookie")
PYEOF

echo "[3/4] 上传服务器并重启..."
scp -q -o BatchMode=yes -i "$KEY" "$PROJ/config.json" "$SERVER:/tmp/config_new.json"
ssh -o BatchMode=yes -i "$KEY" "$SERVER" '
    LINES=$(wc -l < /opt/AutoCheckBJMF/logs/sign_log.txt)
    cp /tmp/config_new.json /opt/AutoCheckBJMF/config.json
    chmod 600 /opt/AutoCheckBJMF/config.json
    rm /tmp/config_new.json
    pm2 restart AutoCheckBJMF >/dev/null
    sleep 18
    echo "--- 本次重启后的日志 ---"
    tail -n +$((LINES+1)) /opt/AutoCheckBJMF/logs/sign_log.txt
    if tail -n +$((LINES+1)) /opt/AutoCheckBJMF/logs/sign_log.txt | grep -q "Login state invalid"; then
        echo "✗ 新 cookie 仍然无效，请重试"
        exit 1
    else
        echo "✓ 无登录失效记录，续期完成"
    fi
'
echo "[4/4] 完成。服务器已用新 cookie 运行。"
