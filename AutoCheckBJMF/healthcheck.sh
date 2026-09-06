#!/usr/bin/env bash
# AutoCheckBJMF 健康检查 + 通知（cron 每 30 分钟，指向运行目录 /opt/AutoCheckBJMF/healthcheck.sh）
# 1) pm2 掉线 / cookie 登录失效 -> TG 告警（状态变化才发，恢复也报）
# 2) 自上次检查以来出现新的「签到成功」-> TG 推送（只推成功记录，失败行留给 /status）
# 凭据与状态文件固定在影子仓 /opt/AutoCheckBJMF_git/（不入运行目录，rsync --delete 不会碰它）
TG_TOKEN_FILE=/opt/AutoCheckBJMF_git/.tg_token
TG_CHAT_FILE=/opt/AutoCheckBJMF_git/.tg_chat
STATE=/opt/AutoCheckBJMF_git/.health_state
SEND_LOG=/opt/AutoCheckBJMF_git/.health_send.log
POS_FILE=/opt/AutoCheckBJMF_git/.log_pos
LOG=/opt/AutoCheckBJMF/logs/sign_log.txt

[ -s "$TG_TOKEN_FILE" ] && [ -s "$TG_CHAT_FILE" ] || exit 0
TOKEN=$(cat "$TG_TOKEN_FILE")
CHAT=$(cat "$TG_CHAT_FILE")

send() {
    # Telegram 单条上限 4096 字符，按字符截断（head -c 会切断多字节汉字）
    MSG=$(printf "%s" "$1" | python3 -c "
import sys
t = sys.stdin.read()
sys.stdout.write(t[:3900] + ('\n…（内容过长，已截断）' if len(t) > 3900 else ''))
")
    {
        echo "[$(date "+%F %T")] sending..."
        curl -s -m 15 "https://api.telegram.org/bot$TOKEN/sendMessage" \
            --data-urlencode "chat_id=$CHAT" --data-urlencode "text=$MSG"
        echo
    } >> "$SEND_LOG" 2>&1
    # 发送日志超过 200KB 截断
    [ -s "$SEND_LOG" ] && [ "$(stat -c %s "$SEND_LOG")" -gt 200000 ] && tail -c 50000 "$SEND_LOG" > "$SEND_LOG.tmp" && mv "$SEND_LOG.tmp" "$SEND_LOG"
    return 0
}

# ---- 1) 健康告警 ----
PM2_OK=$(pm2 jlist 2>/dev/null | python3 -c "
import json, sys
try:
    ps = json.load(sys.stdin)
except Exception:
    ps = []
ok = any(p.get(\"name\") == \"AutoCheckBJMF\" and p.get(\"pm2_env\", {}).get(\"status\") == \"online\" for p in ps)
print(\"yes\" if ok else \"no\")
")

RECENT_BAD=no
if [ -f "$LOG" ]; then
RECENT_BAD=$(python3 - "$LOG" << "PYEOF"
import re, sys
from datetime import datetime, timedelta
try:
    lines = open(sys.argv[1], errors="ignore").read().strip().split("\n")
except FileNotFoundError:
    print("no"); raise SystemExit
now = datetime.now()
cut = now - timedelta(minutes=20)
bad = False
for line in reversed(lines):
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
    if not m:
        continue
    t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    if t < cut:
        break
    if "Login state invalid" in line:
        bad = True
        break
print("yes" if bad else "no")
PYEOF
)
fi

if [ "$PM2_OK" = no ] || [ "$RECENT_BAD" = yes ]; then
    NOW=bad
    REASON=""
    [ "$PM2_OK" = no ] && REASON="pm2 进程非 online"
    [ "$RECENT_BAD" = yes ] && REASON="${REASON:+$REASON；}最近日志有 Login state invalid，cookie 可能已失效"
else
    NOW=good
fi

PREV=$(cat "$STATE" 2>/dev/null || echo good)
if [ "$NOW" != "$PREV" ]; then
    if [ "$NOW" = bad ]; then
        send "⚠️ 班级魔方签到异常
$REASON
处理：WSL 侧 bash AutoCheckBJMF/renew_cookie.sh 扫码续期"
    else
        send "✅ 班级魔方签到已恢复正常"
    fi
    echo "$NOW" > "$STATE"
fi

# ---- 2) 签到成功通知 ----
if [ -f "$LOG" ]; then
    TOTAL=$(wc -l < "$LOG")
    LAST=$(cat "$POS_FILE" 2>/dev/null || echo 0)
    if [ "$TOTAL" -lt "$LAST" ]; then
        LAST=0   # 日志轮转（rename+新建），新文件内容全部是轮转后写入的行
    fi
    if [ "$TOTAL" -gt "$LAST" ]; then
        NEW=$(tail -n +$((LAST + 1)) "$LOG")
        SUCCESS_LINES=$(echo "$NEW" | grep "Result: 签到成功" || true)
        if [ -n "$SUCCESS_LINES" ]; then
            SUMMARY=$(printf "%s\n" "$NEW" | /opt/AutoCheckBJMF/.venv/bin/python /opt/AutoCheckBJMF/tg_bot.py summarize --success-only 2>>"$SEND_LOG")
            # --success-only 过滤后为空（理论上不该发生）就不推，避免空推送
            if [ -n "$SUMMARY" ]; then
                send "🎉 自动签到成功

$SUMMARY"
            fi
        fi
        echo "$TOTAL" > "$POS_FILE"
    fi
fi
