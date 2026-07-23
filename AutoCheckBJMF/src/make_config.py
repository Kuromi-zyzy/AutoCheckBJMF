"""
make_config.py -- AutoCheckBJMF configuration wizard
=====================================================
Interactive terminal-based setup that writes config.json.

Config format:
{
    "classes":      ["123456", "789012"],
    "locations": [{"lat": "39.90000000", "lng": "116.40000000", "acc": "10"}],
    "cookies":      ["remember_student_xxx=..."],
    "scheduletimes": ["auto"],
    "schedule_window_start": "20:00",
    "schedule_window_end":   "23:30",
    "schedule_interval":     5,
    "debug":        false
}
"""

import os
import re
import json

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML
import questionary
from DrissionPage import ChromiumPage

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.rule import Rule

from constants import CONFIG_PATH, COOKIE_KEY, LOGIN_URL, LISTEN_TARGET, MAP_URL
from banner import print_banner

console = Console()


# ---------------------------------------------------------------------------
#  Utility functions
# ---------------------------------------------------------------------------

def prompt_input(message: str, placeholder: str = "", default: str = "") -> str:
    """
    Terminal input with grey placeholder text (via prompt_toolkit).

    Args:
        message     -- prompt text shown to user
        placeholder -- grey hint inside the input box
        default     -- fallback value when user presses Enter with empty input

    Returns:
        User input string, stripped of leading/trailing whitespace.
    """
    placeholder_html = HTML(f'<style color="#888888">{placeholder}</style>') if placeholder else None
    result = prompt(message, placeholder=placeholder_html).strip()
    return result if result else default


def load_existing_config() -> dict:
    """
    Read existing config.json, returning {} if missing or malformed.

    Returns:
        Config dict, or empty dict.
    """
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_config(config: dict):
    """
    Write config dict to config.json (UTF-8, 4-space indent).

    Args:
        config -- full configuration dict
    """
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    console.print(f"\n[bold green]V  配置已保存到:[/bold green] [underline]{CONFIG_PATH}[/underline]")


def print_step_header(step: int, total: int, title: str, subtitle: str = ""):
    """
    Print a uniform step header panel.

    Args:
        step     -- current step number
        total    -- total number of steps
        title    -- step title
        subtitle -- optional description
    """
    step_label = f"步骤 {step}/{total}"
    content = f"[bold white]{title}[/bold white]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    console.print(
        Panel(
            content,
            title=f"[bold yellow] {step_label} [/bold yellow]",
            border_style="yellow",
            padding=(0, 2),
        )
    )


# ---------------------------------------------------------------------------
#  Step 1: Login via browser QR scan, capture class IDs and cookies
# ---------------------------------------------------------------------------

def login_and_capture(existing_cookies: list) -> tuple:
    """
    Open a Chromium browser for WeChat QR login, extract class IDs and cookies.
    Supports adding multiple accounts in a loop.

    Args:
        existing_cookies -- previously collected cookies (to append, not overwrite)

    Returns:
        (class_list, cookie_list)
          class_list  -- deduplicated sorted list of class ID strings
          cookie_list -- list of extracted cookie strings
    """
    class_set = set()
    cookie_list = list(existing_cookies)

    print_step_header(
        1, 3,
        "获取班级 ID 和 Cookie",
        "浏览器将打开，请用微信扫码登录。"
        "班级 ID 和 Cookie 将自动提取。"
    )

    while True:
        answer = questionary.confirm("添加账号？（扫码登录）", default=True).ask()
        if not answer:
            break

        page = ChromiumPage()
        try:
            page.listen.start(LISTEN_TARGET)
            console.print("  [cyan]>[/cyan] 正在打开登录页面，请用微信扫码（120秒超时）...")
            page.get(LOGIN_URL)

            if not page.wait.eles_loaded('t:a@class=media', timeout=120):
                console.print("  [bold red]X[/bold red] 登录超时，请重试")
                page.listen.stop()
                try:
                    page.close()
                except Exception:
                    pass
                continue

            console.print("  [bold green]V[/bold green] 登录成功！正在读取课程列表...")

            a_tags = page.eles('t:a@class=media')
            for a in a_tags:
                href = a.attr('href')
                if href:
                    match = re.search(r'/student/course/(\d+)', href)
                    if match:
                        class_set.add(match.group(1))

            console.print("  [cyan]>[/cyan] 正在抓取 cookie...")
            packet = page.listen.wait(timeout=30)

            if packet:
                cookie_str = packet.request.headers.get('Cookie', '')
                pattern = rf'{COOKIE_KEY}=[^;]+'
                result = re.search(pattern, cookie_str)
                if result:
                    extracted = result.group(0)
                    if extracted not in cookie_list:
                        cookie_list.append(extracted)
                        console.print(f"  [bold green]V[/bold green] Cookie 抓取成功: [dim]{extracted[:40]}...[/dim]")
                    else:
                        console.print("  [yellow]![/yellow]  Cookie 已存在，跳过")
                else:
                    console.print("  [bold red]X[/bold red] 未找到目标 cookie，请检查账号")
            else:
                console.print("  [bold red]X[/bold red] 监听超时，cookie 未捕获")

        finally:
            try:
                page.listen.stop()
            except Exception:
                pass
            try:
                page.close()
            except Exception:
                pass

        console.print(
            f"  [dim]已收集账号: [bold]{len(cookie_list)}[/bold], "
            f"班级: [bold]{len(class_set)}[/bold][/dim]"
        )

    class_list = sorted(class_set)

    # Allow manual entry of additional class IDs
    console.print(f"\n  自动检测到的班级 ID: [bold cyan]{class_list if class_list else '(无)'}[/bold cyan]")
    while True:
        manual = prompt_input("  手动添加班级 ID（留空完成）: ").strip()
        if not manual:
            break
        if manual not in class_list:
            class_list.append(manual)
            console.print(f"  [bold green]V[/bold green] 已添加班级 ID: [cyan]{manual}[/cyan]")

    if not class_list:
        console.print(
            "  [bold red]X[/bold red] 未检测到或未输入班级 ID，"
            "签到工具需要至少一个班级才能运行"
        )

    return class_list, cookie_list


# ---------------------------------------------------------------------------
#  Step 2: Configure GPS locations
# ---------------------------------------------------------------------------

def configure_locations(existing_locations: list) -> list:
    """
    Guide the user through setting up GPS coordinate locations.
    Opens the Tencent map coordinate picker for reference.

    Args:
        existing_locations -- previously configured locations (to append)

    Returns:
        Updated list of location dicts with lat / lng / acc keys.
    """
    locations = list(existing_locations)

    print_step_header(
        2, 3,
        "配置签到定位点",
        "浏览器将打开腾讯地图坐标拾取器，"
        "在地图上点击签到位置获取坐标，然后输入。"
    )

    if not questionary.confirm("现在配置定位点？", default=True).ask():
        console.print("  [yellow]跳过定位配置，使用现有定位点[/yellow]")
        return locations

    map_page = ChromiumPage()
    try:
        console.print("  [cyan]>[/cyan] 正在打开腾讯地图，请在地图上点击签到位置...")
        map_page.get(MAP_URL)
        console.print(
            Panel(
                "[bold]操作说明[/bold]\n"
                "1. 在打开的浏览器地图中，[yellow]点击签到位置[/yellow]\n"
                "2. 页面会显示 [cyan]纬度 (lat)[/cyan] 和 [cyan]经度 (lng)[/cyan]\n"
                "3. 复制数值并输入到下方\n"
                "4. 完成后地图会自动关闭",
                border_style="blue",
                padding=(0, 2),
            )
        )

        while True:
            idx = len(locations) + 1
            add_more = questionary.confirm(
                f"添加定位点 #{idx}？",
                default=True
            ).ask()
            if not add_more:
                break

            console.print(
                f"\n  [bold]定位点 #{idx}[/bold]  "
                "[dim]输入最多8位小数，脚本会自动添加微小偏移[/dim]"
            )

            lat = ""
            while not lat:
                lat = prompt_input("  输入纬度 (lat): ").strip()
                if not re.match(r'^\d+\.\d{4,}$', lat):
                    console.print("  [bold red]X[/bold red] 格式错误，例如 39.90123456（至少4位小数）")
                    lat = ""

            lng = ""
            while not lng:
                lng = prompt_input("  输入经度 (lng): ").strip()
                if not re.match(r'^\d+\.\d{4,}$', lng):
                    console.print("  [bold red]X[/bold red] 格式错误，例如 116.40123456（至少4位小数）")
                    lng = ""

            acc = prompt_input("  输入精度 (acc)，直接回车默认 10: ", default="10")

            locations.append({"lat": lat, "lng": lng, "acc": acc})
            console.print(
                f"  [bold green]V[/bold green] 已添加定位点 #{idx}: "
                f"[cyan]lat={lat}[/cyan]  [cyan]lng={lng}[/cyan]  [dim]acc={acc}[/dim]"
            )

    finally:
        console.print("\n  [cyan]>[/cyan] 定位配置完成，正在关闭地图...")
        try:
            map_page.close()
        except Exception:
            pass

    if not locations:
        console.print(
            "  [bold red]X[/bold red] 未配置定位点，"
            "签到工具需要至少一个定位点才能运行"
        )

    return locations


# ---------------------------------------------------------------------------
#  Step 3: Configure check-in time window
# ---------------------------------------------------------------------------

def configure_schedule_window(existing_config: dict) -> dict:
    """
    Guide the user through setting the check-in time window and scan interval.

    Args:
        existing_config -- previously loaded config dict

    Returns:
        Dict with schedule_window_start, schedule_window_end, schedule_interval
    """
    window = {
        "schedule_window_start": existing_config.get("schedule_window_start", "20:00"),
        "schedule_window_end":   existing_config.get("schedule_window_end", "23:30"),
        "schedule_interval":     existing_config.get("schedule_interval", 5),
    }

    print_step_header(
        3, 3,
        "配置签到时间窗口",
        "设置每天的签到时间范围和扫描频率，"
        "程序会在该时间段内自动检测并签到。"
    )

    console.print("  [dim]当前设置:[/dim]")
    console.print(f"    Start: [cyan]{window['schedule_window_start']}[/cyan]")
    console.print(f"    End:   [cyan]{window['schedule_window_end']}[/cyan]")
    console.print(f"    Interval: [cyan]{window['schedule_interval']}[/cyan] min\n")

    if not questionary.confirm("修改签到时间窗口？", default=False).ask():
        return window

    start_str = ""
    while not start_str:
        start_str = prompt_input(
            "  窗口开始时间 (HH:MM，如 20:00): ",
            default=window["schedule_window_start"]
        ).strip()
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', start_str):
            console.print("  [bold red]X[/bold red] 格式错误！例如: 08:00, 20:00, 22:30")
            start_str = ""

    end_str = ""
    while not end_str:
        end_str = prompt_input(
            "  窗口结束时间 (HH:MM，如 23:30): ",
            default=window["schedule_window_end"]
        ).strip()
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', end_str):
            console.print("  [bold red]X[/bold red] 格式错误！例如: 08:00, 20:00, 22:30")
            end_str = ""

    interval_str = ""
    while not interval_str:
        interval_str = prompt_input(
            "  扫描间隔（分钟）: ",
            default=str(window["schedule_interval"])
        ).strip()
        if not re.match(r'^\d+$', interval_str) or int(interval_str) < 1:
            console.print("  [bold red]X[/bold red] 请输入正整数（如 5, 10, 15）")
            interval_str = ""

    window["schedule_window_start"] = start_str
    window["schedule_window_end"]   = end_str
    window["schedule_interval"]     = int(interval_str)

    console.print(
        f"\n  [bold green]V[/bold green] 签到窗口已设置: "
        f"[cyan]{start_str}[/cyan] -> [cyan]{end_str}[/cyan], "
        f"每 [bold]{interval_str}[/bold] 分钟扫描一次"
    )

    return window


# ---------------------------------------------------------------------------
#  Summary display
# ---------------------------------------------------------------------------

def print_summary(config: dict):
    """
    Display the final config summary as a Rich table.

    Args:
        config -- full configuration dict
    """
    console.print()
    console.rule("[bold yellow]配置摘要[/bold yellow]")

    table = Table(box=box.ROUNDED, border_style="dim", show_header=False, padding=(0, 1))
    table.add_column("Item", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("班级 ID", ", ".join(config["classes"]) if config["classes"] else "[red]未配置[/red]")
    table.add_row("定位点", f"{len(config['locations'])} 个")
    table.add_row("账号", f"{len(config['cookies'])} 个")

    if config.get("schedule_window_start") and config.get("schedule_window_end"):
        window = f"{config['schedule_window_start']} -> {config['schedule_window_end']}"
        table.add_row("签到窗口", f"[cyan]{window}[/cyan]  每 [bold]{config.get('schedule_interval', 5)}[/bold] 分钟")
    elif config.get("scheduletimes"):
        table.add_row("时间", "[cyan]" + "  /  ".join(config["scheduletimes"]) + "[/cyan]")
    else:
        table.add_row("签到窗口", "[yellow]未设置（立即模式）[/yellow]")

    table.add_row("调试模式", "[yellow]开启[/yellow]" if config["debug"] else "[dim]关闭[/dim]")

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
#  Main flow
# ---------------------------------------------------------------------------

def main():
    """
    Configuration wizard main flow:
    1. Print banner
    2. Load existing config (supports append/modify)
    3. Execute 3 config steps
    4. Show summary and save to config.json
    """
    print_banner()
    console.print(
        Panel.fit(
            "[bold white]班级魔方 GPS 自动签到 -- 配置向导[/bold white]\n"
            "[dim]项目: https://github.com/Moeus/AutoCheckBJMF[/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()

    existing = load_existing_config()
    if existing:
        console.print(
            Panel(
                "[yellow]检测到现有配置，将在现有配置基础上修改[/yellow]",
                border_style="yellow",
                padding=(0, 2),
            )
        )
        if questionary.confirm("清除现有配置并重新开始？", default=False).ask():
            existing = {}
            console.print(
                Panel(
                    "[red]现有配置已清除，重新开始配置[/red]",
                    border_style="red",
                    padding=(0, 2),
                )
            )
    else:
        console.print("[dim]未检测到现有配置，将创建新配置[/dim]\n")

    existing_classes   = existing.get("classes", [])
    existing_locations = existing.get("locations", [])
    existing_cookies   = existing.get("cookies", [])
    existing_debug     = existing.get("debug", False)

    console.print()

    # Step 1: Login and capture class IDs + cookies
    class_list, cookie_list = login_and_capture(existing_cookies)

    for cid in existing_classes:
        if cid not in class_list:
            class_list.append(cid)

    console.print()

    # Step 2: Configure locations
    locations = configure_locations(existing_locations)

    console.print()

    # Step 3: Configure time window
    schedule_window = configure_schedule_window(existing)

    console.print()

    # Debug mode
    console.rule("[dim]其他设置[/dim]")
    debug = questionary.confirm(
        "开启调试模式？（详细日志写入 AutoCheckBJMF.log）",
        default=existing_debug
    ).ask()

    # Assemble config
    config = {
        "classes":       class_list,
        "locations":     locations,
        "cookies":       cookie_list,
        "scheduletimes": ["auto"],
        "schedule_window_start": schedule_window["schedule_window_start"],
        "schedule_window_end":   schedule_window["schedule_window_end"],
        "schedule_interval":     schedule_window["schedule_interval"],
        "debug":         debug,
    }

    print_summary(config)

    if questionary.confirm("保存以上配置？", default=True).ask():
        save_config(config)
        console.print(
            Panel(
                "[bold green]  配置完成！[/bold green]\n\n"
                "  [cyan]python main.py[/cyan]   -- 启动定时自动签到\n"
                "  [cyan]python once.py[/cyan]   -- 立即签到一次（应急）",
                border_style="green",
                padding=(1, 4),
            )
        )
    else:
        console.print("[yellow]已取消，配置未保存[/yellow]")


if __name__ == "__main__":
    main()
