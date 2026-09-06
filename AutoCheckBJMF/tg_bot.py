#!/usr/bin/env python3
"""TG bot for AutoCheckBJMF：/checkin 立即签到一次，/status 查看状态。

由 pm2 托管常驻（long polling getUpdates）。凭据从影子仓 .tg_token/.tg_chat 读取，
仅响应白名单 chat_id。

`summarize` 子命令：从 stdin 读日志行，输出人类可读摘要（healthcheck 推送复用）。
"""
import json
import math
import re
import subprocess
import sys
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
CLASS_LABEL = {"139098": "139098（目标班）", "139198": "139198（测试班）"}

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


def strip_ts(line: str) -> str:
    return line.split(" - ", 1)[-1] if " - " in line else line


def read_new_log(before: int = 0, tail: int | None = None) -> list[str]:
    """完整日志行（含时间戳前缀）。before=字节偏移取增量；tail=N 取末尾 N 行。"""
    if not LOG.exists():
        return []
    with open(LOG, errors="ignore") as f:
        if tail is None:
            f.seek(before)
            return [l.rstrip("\n") for l in f if l.strip()]
        return [l.rstrip("\n") for l in f.readlines()[-tail:] if l.strip()]


def nearest_spot(coord: tuple[float, float] | None) -> str:
    """坐标 → 最近的配置定位点描述。"""
    if not coord:
        return ""
    try:
        cfg = json.load(open(RUN_DIR / "config.json"))
        spots = [(float(p["lat"]), float(p["lng"])) for p in cfg.get("locations", [])]
    except Exception:
        return ""
    if not spots:
        return ""
    dists = [math.hypot(coord[0] - a, coord[1] - b) for a, b in spots]
    return f"📍 定位点 {dists.index(min(dists)) + 1} 附近"


def class_tag(cls: str | None) -> str:
    return CLASS_LABEL.get(cls, cls or "未知班级")


def humanize(raw_lines: list[str]) -> list[str]:
    """机器日志行 → 每条签到一行人话：`✅ 139198（测试班）· 签到成功 · 📍 定位点 2 附近`"""
    records = []
    cur_cls, cur_coord = None, None
    for line in raw_lines:
        m = re.search(r"Class\[(\d+)\]", line)
        if m:
            cur_cls = m.group(1)
        m = re.search(r"Coord\[([-\d.]+),\s*([-\d.]+)\]", line)
        if m:
            cur_coord = (float(m.group(1)), float(m.group(2)))
        m = re.search(r"Result: (.+)", line)
        if m:
            records.append((cur_cls, cur_coord, m.group(1).strip()))
            cur_cls, cur_coord = None, None
    out = []
    for cls, coord, result in records:
        icon = "✅" if result == "签到成功" else "⚠️"
        parts = [f"{icon} {class_tag(cls)}", result]
        spot = nearest_spot(coord)
        if spot:
            parts.append(spot)
        out.append(" · ".join(parts))
    return out


def summarize(raw_lines: list[str]) -> str:
    return "\n".join(humanize([strip_ts(l) for l in raw_lines]))


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
    lines = [strip_ts(l) for l in read_new_log(before=before)]
    if any("Result: 签到成功" in l for l in lines):
        send(chat_id, "🎉 立即签到完成\n\n" + summarize_lines_keep(lines))
    elif any("Login state invalid" in l for l in lines):
        send(chat_id, "❌ 签到失败：登录已失效，cookie 可能过期\n"
                      "👉 WSL 侧运行 renew_cookie.sh 重新扫码")
    elif any("CheckInID" in l for l in lines):
        send(chat_id, "⚠️ 发现签到任务，但未签成\n\n"
                      + summarize_lines_keep(lines)
                      + "\n\n（拍照签到等类型暂不支持，请手动处理）")
    else:
        send(chat_id, "✅ 轮询完成，当前没有待签任务")


def summarize_lines_keep(lines: list[str]) -> str:
    return "\n".join(humanize(lines)) or "（无详情）"


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

    items = []
    for line in read_new_log(tail=15):
        hm = re.match(r"\d{4}-\d{2}-\d{2} (\d{2}:\d{2})", line)
        hm = hm.group(1) if hm else "--:--"
        rest = strip_ts(line)
        if "Login state invalid" in rest:
            items.append(f"· {hm} ❌ 登录失效")
        elif "Result: " in rest:
            result = rest.split("Result: ")[-1].strip()
            m = re.search(r"Class\[(\d+)\]", rest)
            icon = "✅" if result == "签到成功" else "⚠️"
            items.append(f"· {hm} {icon} {class_tag(m.group(1) if m else None)} {result}")
        elif "Idle heartbeat" in rest:
            items.append(f"· {hm} 💤 窗口内无签到任务")
        elif "sleeping until next window" in rest:
            items.append(f"· {hm} 💤 已过窗口，睡到明天")
        elif "Interval-scan mode" in rest:
            items.append(f"· {hm} ▶️ 服务启动")
    body = "\n".join(items[-6:]) or "（暂无动态）"
    running = "🟢 运行中" if status == "online" else f"🔴 {status}"
    send(chat_id, f"📊 签到服务状态：{running}\n\n最近动态：\n{body}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        print(summarize([l.rstrip("\n") for l in sys.stdin if l.strip()]))
        return
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
                send(chat["id"], "可用指令：\n/checkin — 立即签到一次\n/status — 查看服务状态")


if __name__ == "__main__":
    main()
