"""
main.py -- AutoCheckBJMF scheduled check-in program
===================================================
Reads config.json, registers scheduled tasks or runs interval-scan mode,
and automatically signs in all classes/accounts at specified times.

Usage:
    python main.py

If config.json is missing, run make_config.py first.
"""

import random
import requests
import re
import time
import os
import sys

# -- UTF-8 encoding fix for Windows GBK terminals --
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import logging
import schedule
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.rule import Rule

from constants import CONFIG_PATH, COOKIE_KEY, BASE_URL, USER_AGENT, LOG_DIR
from banner import console, print_banner


# ---------------------------------------------------------------------------
#  Configuration loading
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """
    Load and validate config.json.

    Returns:
        Configuration dict with classes / locations / cookies / scheduletimes / debug

    Raises:
        SystemExit if file is missing or malformed.
    """
    if not os.path.exists(CONFIG_PATH):
        console.print(Panel(
            "[bold red]X  config.json not found[/bold red]\n"
            "Please run [cyan]python make_config.py[/cyan] first to generate the config.",
            border_style="red", padding=(0, 2)
        ))
        input("Press Enter to exit...")
        raise SystemExit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]X  config.json parse error:[/bold red] {e}")
            input("Press Enter to exit...")
            raise SystemExit(1)

    required_keys = ["classes", "locations", "cookies"]
    for key in required_keys:
        if key not in cfg:
            console.print(f"[bold red]X  config.json missing required key:[/bold red] [cyan]{key}[/cyan]")
            input("Press Enter to exit...")
            raise SystemExit(1)

    cfg.setdefault("scheduletimes", ["auto"])
    cfg.setdefault("schedule_window_start", "20:00")
    cfg.setdefault("schedule_window_end", "23:30")
    cfg.setdefault("schedule_interval", 5)

    return cfg


# ---------------------------------------------------------------------------
#  Logger setup
# ---------------------------------------------------------------------------

def setup_logger(debug: bool) -> logging.Logger:
    """
    Initialize the logger. Always writes sign_log.txt (UTF-8, append).
    In debug mode also writes AutoCheckBJMF.log with full level info.

    Args:
        debug -- enable debug logging

    Returns:
        Configured logging.Logger instance
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("AutoCheckBJMF")
    logger.setLevel(logging.INFO)

    sign_handler = logging.FileHandler(
        os.path.join(LOG_DIR, "sign_log.txt"), encoding="utf-8", mode="a"
    )
    sign_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(sign_handler)

    if debug:
        debug_handler = logging.FileHandler(
            os.path.join(LOG_DIR, "AutoCheckBJMF.log"), encoding="utf-8"
        )
        debug_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(debug_handler)

    return logger


# ---------------------------------------------------------------------------
#  GPS coordinate helpers
# ---------------------------------------------------------------------------

def modify_decimal_part(num: float | str) -> float:
    """
    Apply a random micro-offset to the 4th-8th decimal digits of a coordinate.

    This gives each account a slightly different GPS reading to avoid
    detection by the platform.

    Args:
        num -- original latitude or longitude (float or string)

    Returns:
        Offset coordinate as float
    """
    num = float(num)
    num_str = f"{num:.8f}"
    decimal_idx = num_str.find('.')

    decimal_part = num_str[decimal_idx + 4: decimal_idx + 9]
    decimal_value = int(decimal_part)

    random_offset = random.randint(-15000, 15000)
    new_decimal_value = abs(decimal_value + random_offset)
    new_decimal_str = f"{new_decimal_value:05d}"

    new_num_str = num_str[:decimal_idx + 4] + new_decimal_str + num_str[decimal_idx + 9:]
    return float(new_num_str)


def pick_location(locations: list) -> dict:
    """
    Pick a random location from the list.

    Args:
        locations -- list of location dicts with lat / lng / acc keys

    Returns:
        A randomly selected location dict
    """
    return random.choice(locations)


# ---------------------------------------------------------------------------
#  Core check-in logic
# ---------------------------------------------------------------------------

def qiandao(
    class_id: str,
    cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger
) -> tuple:
    """
    Perform check-in for a single class across all accounts, with retry for failures.

    Args:
        class_id  -- class ID string
        cookies   -- list of cookie strings
        locations -- list of location dicts
        debug     -- debug mode flag
        logger    -- logger instance

    Returns:
        (error_cookies, null_count, success_count)
          error_cookies -- cookies that failed (for retry)
          null_count    -- count of malformed cookies
          success_count -- count of successful accounts
    """
    url = f"{BASE_URL}/student/course/{class_id}/punchs"
    error_cookies = []
    null_count = 0
    success_count = 0

    for uid, raw_cookie in enumerate(cookies):
        username_match = re.search(r'username=[^;]+', raw_cookie)
        username_tag = f" <{username_match.group(0).split('=')[1]}>" if username_match else ""

        time.sleep(random.uniform(1, 3))
        console.print(
            f"\r  [bold yellow]* {uid + 1} *[/bold yellow] {username_tag} [bold yellow]Starting check-in * {uid + 1} *[/bold yellow]"
        )

        cookie_match = re.search(rf'{COOKIE_KEY}=[^;]+', raw_cookie)
        if not cookie_match:
            null_count += 1
            console.print(f"  [bold red]X[/bold red] Invalid cookie for account {uid + 1}")
            continue

        extracted_cookie = cookie_match.group(0)
        if debug:
            console.print(f"  [dim][Debug] Cookie: {extracted_cookie}[/dim]")

        headers = {
            'User-Agent':      USER_AGENT,
            'Accept':          ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                                'image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;'
                                'q=0.8,application/signed-exchange;v=b3;q=0.7'),
            'X-Requested-With': 'com.tencent.mm',
            'Referer':         f'{BASE_URL}/student/course/{class_id}',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh-SG;q=0.9,zh;q=0.8,en-SG;q=0.7,en-US;q=0.6,en;q=0.5',
            'Cookie':          extracted_cookie
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException as e:
            console.print(f"  [bold red]X[/bold red] Network request failed: {e}")
            error_cookies.append(raw_cookie)
            continue

        console.print(f"  [cyan]> [/cyan]Class [bold]{class_id}[/bold] response: [dim]{response.status_code}[/dim]")

        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('title')
        if not title_tag or "\u51fa\u9519" in title_tag.text:
            console.print(f"  [bold red]X[/bold red] Login state invalid (account {uid + 1}), queued for retry")
            logger.error(f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | Login state invalid")
            error_cookies.append(raw_cookie)
            continue

        gps_btn = soup.find('a', id=re.compile(r'^gps_btn_\d+$'))
        all_matches = []
        if gps_btn:
            gps_id = re.compile(r'\d+').search(gps_btn.get('id')).group(0)
            all_matches.append(gps_id)

        console.print(f"  [cyan]> [/cyan]Found GPS check-in IDs: [bold cyan]{all_matches}[/bold cyan]")

        if not all_matches:
            console.print(f"  [yellow]![/yellow]  Class [bold]{class_id}[/bold] has no active check-in tasks.")
            logger.info(f"Class[{class_id}] | No active check-in tasks")
            continue

        for match_id in all_matches:
            loc = pick_location(locations)
            new_lat = modify_decimal_part(loc["lat"])
            new_lng = modify_decimal_part(loc["lng"])
            acc = loc["acc"]

            sign_url = f"{BASE_URL}/student/punchs/course/{class_id}/{match_id}"
            payload = {
                'id':       match_id,
                'lat':      new_lat,
                'lng':      new_lng,
                'acc':      acc,
                'res':      '',
                'gps_addr': ''
            }

            try:
                sign_resp = requests.post(sign_url, headers=headers, data=payload, timeout=15)
            except requests.RequestException as e:
                console.print(f"  [bold red]X[/bold red] Check-in request failed: {e}")
                error_cookies.append(raw_cookie)
                continue

            console.print(
                f"  [cyan]> [/cyan]Check-in sent: "
                f"ID[[bold]{match_id}[/bold]] "
                f"coord[[cyan]{new_lat:.6f}, {new_lng:.6f}[/cyan]] "
                f"alt[[dim]{acc}[/dim]]"
            )
            logger.info(
                f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | "
                f"CheckInID[{match_id}] | Coord[{new_lat},{new_lng}]"
            )

            if sign_resp.status_code == 200:
                result_soup = BeautifulSoup(sign_resp.text, 'html.parser')
                div_tag = result_soup.find('div', id='title')
                if div_tag:
                    result_text = div_tag.text.strip()
                    if result_text == "\u7b7e\u5230\u6210\u529f":
                        console.print(f"  [bold green]V[/bold green] Result: [bold green]{result_text}[/bold green]")
                        logger.info(
                            f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | Result: {result_text}"
                        )
                        success_count += 1
                        break
                    else:
                        console.print(f"  [yellow]![/yellow] Result: [yellow]{result_text}[/yellow]")
                        logger.info(
                            f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | Result: {result_text}"
                        )
                else:
                    console.print(f"  [yellow]![/yellow] No result tag found, check-in may have succeeded")
                    logger.warning(
                        f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | No result tag"
                    )
            else:
                console.print(
                    f"  [bold red]X[/bold red] Check-in failed, "
                    f"status [red]{sign_resp.status_code}[/red], queued for retry"
                )
                logger.error(
                    f"UID[{uid + 1}{username_tag}] | Class[{class_id}] | "
                    f"Request failed {sign_resp.status_code}"
                )
                error_cookies.append(raw_cookie)

    return error_cookies, null_count, success_count


def retry_with_backoff(
    class_id: str,
    error_cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger,
    delay_seconds: int,
    attempt_label: str
) -> list:
    """
    Retry failed cookies after a delay.

    Args:
        class_id      -- class ID
        error_cookies -- cookies that failed
        locations     -- location list
        debug         -- debug mode
        logger        -- logger
        delay_seconds -- how long to wait before retrying
        attempt_label -- description for console output

    Returns:
        Remaining error cookies after retry
    """
    console.print(
        f"\n  [yellow]![/yellow] {len(error_cookies)} account(s) failed, "
        f"retrying in {delay_seconds}s... ({attempt_label})"
    )
    time.sleep(delay_seconds)
    error_cookies, _, _ = qiandao(class_id, error_cookies, locations, debug, logger)
    return error_cookies


def run_all_classes(
    classes: list,
    cookies: list,
    locations: list,
    debug: bool,
    logger: logging.Logger
):
    """
    Iterate all classes, perform check-in for each, retry failures up to 2 times.

    Args:
        classes   -- list of class IDs
        cookies   -- list of cookie strings
        locations -- list of location dicts
        debug     -- debug mode
        logger    -- logger instance
    """
    console.rule(f"[bold cyan]Check-in start  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/bold cyan]")
    console.print(
        f"  Classes: [bold]{len(classes)}[/bold]  "
        f"Accounts: [bold]{len(cookies)}[/bold]  "
        f"Locations: [bold]{len(locations)}[/bold]"
    )

    for class_id in classes:
        console.print(f"\n  [cyan]> [/cyan]Checking in class: [bold cyan]{class_id}[/bold cyan]")
        error_cookies, null_count, success_count = qiandao(
            class_id, cookies, locations, debug, logger
        )

        # 1st retry: after 30s
        if error_cookies:
            error_cookies = retry_with_backoff(
                class_id, error_cookies, locations, debug, logger, 30, "1st retry"
            )

        # 2nd retry: after 5 minutes
        if error_cookies:
            error_cookies = retry_with_backoff(
                class_id, error_cookies, locations, debug, logger, 300, "2nd retry"
            )

        if error_cookies:
            console.print(Panel(
                f"[bold red]X  Class {class_id}: some accounts still failed[/bold red]\n"
                "Check whether cookies have expired or the network is unreachable.",
                border_style="red", padding=(0, 2)
            ))
        elif null_count > 0:
            console.print(
                f"\n  [yellow]![/yellow] Class [bold]{class_id}[/bold]: "
                f"{null_count} invalid cookie(s), check config."
            )
        else:
            console.print(Panel(
                f"[bold green]V  Class {class_id}: all check-ins successful![/bold green]",
                border_style="green", padding=(0, 2)
            ))

    console.rule("[dim]Check-in complete[/dim]")


# ---------------------------------------------------------------------------
#  Countdown display
# ---------------------------------------------------------------------------

def show_countdown(schedule_times: list):
    """
    Show a live countdown to the nearest scheduled task.
    Refreshes every second when < 5 minutes remain, otherwise every minute.

    Args:
        schedule_times -- list of "HH:MM" time strings
    """
    now = time.time()

    next_stamps = []
    for t_str in schedule_times:
        hour, minute = map(int, t_str.split(":"))
        today = time.strftime("%Y-%m-%d", time.localtime(now))
        target_struct = time.strptime(f"{today} {hour:02d}:{minute:02d}:00", "%Y-%m-%d %H:%M:%S")
        stamp = time.mktime(target_struct)
        if stamp < now:
            stamp += 24 * 3600
        next_stamps.append((stamp, t_str))

    next_stamp, next_time_str = min(next_stamps, key=lambda x: x[0])
    remaining = int(next_stamp - now)

    hours, rem = divmod(remaining, 3600)
    minutes, seconds = divmod(rem, 60)
    current = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))

    if remaining < 300:
        console.print(
            f"\r  Clock  Current [dim]{current}[/dim]  |  "
            f"Next [bold cyan]{next_time_str}[/bold cyan]  |  "
            f"Remaining [bold yellow]{minutes}[/bold yellow] min [bold yellow]{seconds}[/bold yellow] sec   ",
            end=""
        )
        time.sleep(1)
    else:
        console.print(
            f"\r  Clock  Current [dim]{current}[/dim]  |  "
            f"Next [bold cyan]{next_time_str}[/bold cyan]  |  "
            f"Remaining [bold yellow]{hours}[/bold yellow] hr [bold yellow]{minutes}[/bold yellow] min   ",
            end=""
        )
        time.sleep(60)


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def main():
    """
    Entry point:
    1. Load config
    2. Init logger
    3. Register schedule tasks and loop (fixed-time mode)
       or run interval-scan loop (auto mode)
    """
    print_banner()
    console.print(Panel(
        "[bold white]AutoCheckBJMF -- ClassMagic GPS Auto Check-in[/bold white]  [dim]Scheduled mode[/dim]\n"
        "[dim]Project: https://github.com/Moeus/AutoCheckBJMF[/dim]",
        border_style="cyan", padding=(0, 4)
    ))

    cfg = load_config()
    classes        = cfg["classes"]
    locations      = cfg["locations"]
    cookies        = cfg["cookies"]
    schedule_times = cfg["scheduletimes"]
    debug          = cfg.get("debug", False)

    logger = setup_logger(debug)

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Class IDs", ", ".join(classes) if classes else "[red]Not configured[/red]")
    table.add_row("Accounts", str(len(cookies)))
    table.add_row("Locations", str(len(locations)))
    if schedule_times:
        if schedule_times[0] == "auto":
            win = f"{cfg.get('schedule_window_start', '20:00')} - {cfg.get('schedule_window_end', '23:30')}"
            table.add_row("Scan window", f"[cyan]{win}[/cyan]  every [bold]{cfg.get('schedule_interval', 5)}[/bold] min")
        else:
            table.add_row("Times", "[cyan]" + "  /  ".join(schedule_times) + "[/cyan]")
    else:
        table.add_row("Times", "[yellow]Not set (immediate)[/yellow]")
    table.add_row("Debug mode", "[yellow]On[/yellow]" if debug else "[dim]Off[/dim]")
    console.print(table)

    def job():
        run_all_classes(classes, cookies, locations, debug, logger)
        if schedule_times:
            console.print("\n  [dim]*  Check-in round finished, waiting for next trigger...[/dim]\n")

    is_auto = (schedule_times and schedule_times[0] == "auto")

    if not is_auto and schedule_times:
        # Fixed-time scheduled mode
        for t_str in schedule_times:
            schedule.every().day.at(t_str).do(job)
            console.print(f"  [bold green]V[/bold green] Registered task: daily at [bold cyan]{t_str}[/bold cyan]")
        console.print(f"\n  [bold green]*  Scheduled check-in running. Press Ctrl+C to stop.[/bold green]\n")
        while True:
            schedule.run_pending()
            show_countdown(schedule_times)
    else:
        # Interval-scan mode (auto)
        win_start = cfg.get("schedule_window_start", "20:00")
        win_end   = cfg.get("schedule_window_end", "23:30")
        interval  = cfg.get("schedule_interval", 5)

        sh, sm = map(int, win_start.split(":"))
        eh, em = map(int, win_end.split(":"))
        start_minutes = sh * 60 + sm
        end_minutes   = eh * 60 + em

        console.print(
            f"  [bold green]*  Interval-scan mode active, checking {win_start}-{win_end} every {interval} min[/bold green]\n"
        )

        last_scan = None
        while True:
            now = datetime.now()
            current_minutes = now.hour * 60 + now.minute

            if start_minutes <= current_minutes < end_minutes:
                if last_scan is None or (now - last_scan).total_seconds() >= interval * 60:
                    last_scan = now
                    run_all_classes(classes, cookies, locations, debug, logger)
                    console.print(f"  [dim]Next scan in {interval} minutes...[/dim]")

                # Sleep in short increments so we can respond to window end quickly
                sleep_time = min(60, interval * 60 - (datetime.now() - last_scan).total_seconds())
                if sleep_time > 0:
                    time.sleep(sleep_time)

            elif current_minutes < start_minutes:
                wait_minutes = start_minutes - current_minutes
                console.print(
                    f"  [dim]Check-in window starts in {wait_minutes // 60}h{wait_minutes % 60}m, waiting...[/dim]"
                )
                time.sleep(min(wait_minutes * 60, 1800))

            else:
                console.print("  [dim]Check-in window has ended. Exiting. See you tomorrow![/dim]")
                break


if __name__ == "__main__":
    main()
