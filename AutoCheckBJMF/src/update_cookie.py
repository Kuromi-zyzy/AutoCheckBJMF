"""
更新 Cookie 脚本
打开浏览器 → 微信扫码 → 自动抓取 cookie → 写入 config.json
不影响班级、定位、时间等其他配置
"""

import os
import re
import json
import sys

if sys.stdout is not None and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from DrissionPage import ChromiumPage
from rich.console import Console

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
COOKIE_KEY = "remember_student_59ba36addc2b2f9401580f014c7f58ea4e30989d"
LOGIN_URL = "https://bj.k8n.cn/login/qr/weixin/student/2"
LISTEN_TARGET = "https://bj.k8n.cn"

console = Console()


def main():
    if not os.path.exists(CONFIG_PATH):
        console.print("[bold red]config.json 不存在，请先运行配置向导[/bold red]")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    existing_cookies = cfg.get("cookies", [])

    console.print("[bold cyan]=== 更新 Cookie ===[/bold cyan]")
    console.print(f"当前已有 [bold]{len(existing_cookies)}[/bold] 个账号 cookie\n")

    new_cookies = []
    page = None
    try:
        page = ChromiumPage()
        page.listen.start(LISTEN_TARGET)
        console.print("[cyan]>[/cyan] 正在打开登录页面，请用微信扫码（120秒超时）...")
        page.get(LOGIN_URL)

        if not page.wait.eles_loaded('t:a@class=media', timeout=120):
            console.print("[bold red]X[/bold red] 登录超时，请重试")
            return

        console.print("[bold green]V[/bold green] 登录成功！正在抓取 cookie...")

        packet = page.listen.wait(timeout=30)
        if packet:
            cookie_str = packet.request.headers.get('Cookie', '')
            pattern = rf'{COOKIE_KEY}=[^;]+'
            result = re.search(pattern, cookie_str)
            if result:
                extracted = result.group(0)
                new_cookies.append(extracted)
                console.print(f"[bold green]V[/bold green] Cookie 抓取成功: [dim]{extracted[:40]}...[/dim]")
            else:
                console.print("[bold red]X[/bold red] 未找到目标 cookie，请检查账号")
                return
        else:
            console.print("[bold red]X[/bold red] 监听超时，cookie 未捕获")
            return

    except Exception as e:
        console.print(f"[bold red]X[/bold red] 出错: {e}")
        return
    finally:
        try:
            page.listen.stop()
        except Exception:
            pass
        try:
            page.close()
        except Exception:
            pass

    if new_cookies:
        cfg["cookies"] = new_cookies
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        console.print(f"\n[bold green]V[/bold green] 已保存！新 cookie 已写入 config.json")
        console.print(f"[dim]班级: {cfg.get('classes', [])}[/dim]")
        console.print(f"[dim]定位: {len(cfg.get('locations', []))} 个[/dim]")
    else:
        console.print("\n[bold red]X[/bold red] 未抓取到 cookie，配置未修改")


if __name__ == "__main__":
    main()
