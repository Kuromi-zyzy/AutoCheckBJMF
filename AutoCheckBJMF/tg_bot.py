#!/usr/bin/env python3
"""TG bot for AutoCheckBJMF：/checkin 立即签到一次，/status 查看状态。

由 pm2 托管常驻（long polling getUpdates）。凭据从影子仓 .tg_token/.tg_chat 读取，
仅响应白名单 chat_id。
"""
import json
import subprocess
import time
from pathlib import Path

import requests

TOKEN_FILE = Path("/opt/AutoCheckBJMF_git/.tg_token")
CHAT_FILE = Path("/opt/AutoCheckBJMF_git/.tg_chat")
RUN_DIR = Path("/opt/AutoCheckBJMF")
LOG = RUN_DIR / "logs/sign_log.txt"
PY = RUN_DIR / ".venv/bin/python"

TOKEN = TOKEN_FILE.read_text().strip()
ALLOWED = {int(CHAT_FILE.read_text().strip())}
CLASS_LABEL = {"139098": "139098·目标班", "139198": "139198·测试班"}

CHECKIN_SNIPPET = (
    "import sys; sys.path.insert(0, 'src'); "
    "from main import load_config, setup_logger, run_all_classes; "
    "cfg = load_config(); "
    "run_all_classes(cfg['classes'], cfg['cookies'], cfg['locations'], "
    "cfg.get('debug', False), setup_logger(cfg.get('debug', False)))"
)


def api(method: str, timeout: int = 35, **params):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}",
                      data=params, timeout=timeout)
    return r.json()


def send(chat_id: int, text: str):
    try:
        api("sendMessage", timeout=20, chat_id=chat_id, text=text)
    except Exception as e:
        print(f"send failed: {e}", flush=True)


def label(line: str) -> str:
    for cid, tag in CLASS_LABEL.items():
        line = line.replace(f"Class[{cid}]", f"Class[{tag}]")
    return line


def tail_new_log(before: int) -> list[str]:
    if not LOG.exists():
        return []
    with open(LOG, errors="ignore") as f:
        f.seek(before)
        content = f.read()
    return [label(l.split(" - ", 1)[-1])
            for l in content.strip().splitlines() if " - " in l]


def do_checkin(chat_id: int):
    send(chat_id, "⏳ 正在立即签到一次（含失败重试，最长约 4 分钟）…")
    before = LOG.stat().st_size if LOG.exists() else 0
    try:
        subprocess.run([str(PY), "-c", CHECKIN_SNIPPET],
                       cwd=str(RUN_DIR), capture_output=True,
                       text=True, timeout=240)
    except subprocess.TimeoutExpired:
        send(chat_id, "⌛ 签到轮询超时（可能在退避重试），稍后用 /status 查看")
        return
    lines = tail_new_log(before)
    if any("Result: 签到成功" in l for l in lines):
        keep = [l for l in lines if "CheckInID" in l or "Result" in l]
        send(chat_id, "🎉 立即签到完成\n" + "\n".join(keep))
    elif any("Login state invalid" in l for l in lines):
        send(chat_id, "❌ 签到失败：登录态无效，cookie 可能已过期\n"
                      "处理：WSL 侧 bash AutoCheckBJMF/renew_cookie.sh 扫码续期")
    elif any("CheckInID" in l for l in lines):
        results = [l.split("Result: ")[-1].strip()
                   for l in lines if "Result: " in l]
        uniq = "；".join(dict.fromkeys(results)) or "结果未知"
        send(chat_id, "⚠️ 发现签到任务，但未签成：\n"
                      f"{uniq}\n"
                      "（拍照签到等类型脚本暂不支持，请手动签到）")
    else:
        summary = "\n".join(f"· {l}" for l in lines[-5:]) or "（本轮无任何日志活动）"
        send(chat_id, f"✅ 签到轮询完成，当前无待签任务\n{summary}")


def do_status(chat_id: int):
    status = "?"
    try:
        out = subprocess.run(["pm2", "jlist"], capture_output=True,
                             text=True, timeout=15).stdout
        for p in json.loads(out):
            if p.get("name") == "AutoCheckBJMF":
                status = p["pm2_env"].get("status", "?")
    except Exception as e:
        status = f"查询失败({e})"
    lines = tail_new_log(LOG.stat().st_size - min(2000, LOG.stat().st_size)) if LOG.exists() else []
    body = "\n".join(f"· {l}" for l in lines[-5:]) or "（空）"
    send(chat_id, f"📊 AutoCheckBJMF 进程: {status}\n最近日志:\n{body}")


def main():
    print(f"bot started, allowed={ALLOWED}", flush=True)
    offset = 0
    while True:
        try:
            data = api("getUpdates", timeout=40, offset=offset)
        except Exception as e:
            print(f"getUpdates error: {e}", flush=True)
            time.sleep(5)
            continue
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            chat = msg.get("chat", {})
            text = (msg.get("text") or "").strip()
            if chat.get("id") not in ALLOWED or not text.startswith("/"):
                continue
            cmd = text.split()[0].split("@")[0]
            if cmd == "/checkin":
                do_checkin(chat["id"])
            elif cmd == "/status":
                do_status(chat["id"])
            else:
                send(chat["id"], "可用指令：\n/checkin — 立即签到一次\n/status — 查看进程与最近日志")


if __name__ == "__main__":
    main()
