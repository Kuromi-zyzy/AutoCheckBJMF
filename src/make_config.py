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
    console.print(f"\n[bold green]V  Config saved to:[/bold green] [underline]{CONFIG_PATH}[/underline]")


def print_step_header(step: int, total: int, title: str, subtitle: str = ""):
    """
    Print a uniform step header panel.

    Args:
        step     -- current step number
        total    -- total number of steps
        title    -- step title
        subtitle -- optional description
    """
    step_label = f"Step {step}/{total}"
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
        "Get Class IDs & Cookies",
        "A browser will open. Scan the QR code with WeChat to log in. "
        "Class IDs and cookies will be extracted automatically."
    )

    while True:
        answer = questionary.confirm("Add (another) account? (scan QR to log in)", default=True).ask()
        if not answer:
            break

        page = ChromiumPage()
        try:
            page.listen.start(LISTEN_TARGET)
            console.print("  [cyan]> [/cyan]Opening login page, scan QR with WeChat (120s timeout)...")
            page.get(LOGIN_URL)

            if not page.wait.eles_loaded('t:a@class=media', timeout=120):
                console.print("  [bold red]X[/bold red] Login timeout, please retry.")
                page.listen.stop()
                try:
                    page.close()
                except Exception:
                    pass
                continue

            console.print("  [bold green]V[/bold green] Login successful! Reading course list...")

            a_tags = page.eles('t:a@class=media')
            for a in a_tags:
                href = a.attr('href')
                if href:
                    match = re.search(r'/student/course/(\d+)', href)
                    if match:
                        class_set.add(match.group(1))

            console.print("  [cyan]> [/cyan]Waiting to capture cookie...")
            packet = page.listen.wait(timeout=30)

            if packet:
                cookie_str = packet.request.headers.get('Cookie', '')
                pattern = rf'{COOKIE_KEY}=[^;]+'
                result = re.search(pattern, cookie_str)
                if result:
                    extracted = result.group(0)
                    if extracted not in cookie_list:
                        cookie_list.append(extracted)
                        console.print(f"  [bold green]V[/bold green] Cookie captured: [dim]{extracted[:40]}...[/dim]")
                    else:
                        console.print("  [yellow]![/yellow]  Cookie already exists, skipped.")
                else:
                    console.print("  [bold red]X[/bold red] Target cookie not found, check account.")
            else:
                console.print("  [bold red]X[/bold red] Listen timeout, cookie not captured.")

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
            f"  [dim]Accounts collected: [bold]{len(cookie_list)}[/bold], "
            f"Classes: [bold]{len(class_set)}[/bold][/dim]"
        )

    class_list = sorted(class_set)

    # Allow manual entry of additional class IDs
    console.print(f"\n  Auto-detected class IDs: [bold cyan]{class_list if class_list else '(none)'}[/bold cyan]")
    while True:
        manual = prompt_input("  Manually add class ID (leave empty to finish): ").strip()
        if not manual:
            break
        if manual not in class_list:
            class_list.append(manual)
            console.print(f"  [bold green]V[/bold green] Added class ID: [cyan]{manual}[/cyan]")

    if not class_list:
        console.print(
            "  [bold red]X[/bold red] No class IDs detected or entered. "
            "The check-in tool will not work without at least one class."
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
        "Configure Check-in Locations",
        "A browser will open Tencent Map Coordinate Picker. "
        "Click on the map to get coordinates, then enter them here."
    )

    if not questionary.confirm("Configure locations now?", default=True).ask():
        console.print("  [yellow]Skipping location config, using existing locations.[/yellow]")
        return locations

    map_page = ChromiumPage()
    try:
        console.print("  [cyan]> [/cyan]Opening Tencent coordinate picker, click a location on the map...")
        map_page.get(MAP_URL)
        console.print(
            Panel(
                "[bold]Instructions[/bold]\n"
                "1. In the opened browser map, [yellow]click the check-in location[/yellow]\n"
                "2. The page will show [cyan]latitude (lat)[/cyan] and [cyan]longitude (lng)[/cyan]\n"
                "3. Copy the values and enter them below\n"
                "4. The map will close automatically when you finish",
                border_style="blue",
                padding=(0, 2),
            )
        )

        while True:
            idx = len(locations) + 1
            add_more = questionary.confirm(
                f"Add location #{idx}?",
                default=True
            ).ask()
            if not add_more:
                break

            console.print(
                f"\n  [bold]Location #{idx}[/bold]  "
                "[dim]Enter up to 8 decimal places; the script will apply micro-offsets automatically![/dim]"
            )

            lat = ""
            while not lat:
                lat = prompt_input("  Enter latitude (lat): ").strip()
                if not re.match(r'^\d+\.\d{4,}$', lat):
                    console.print("  [bold red]X[/bold red] Invalid format, e.g. 39.90123456 (at least 4 decimals)")
                    lat = ""

            lng = ""
            while not lng:
                lng = prompt_input("  Enter longitude (lng): ").strip()
                if not re.match(r'^\d+\.\d{4,}$', lng):
                    console.print("  [bold red]X[/bold red] Invalid format, e.g. 116.40123456 (at least 4 decimals)")
                    lng = ""

            acc = prompt_input("  Enter altitude (acc), press Enter for default 10: ", default="10")

            locations.append({"lat": lat, "lng": lng, "acc": acc})
            console.print(
                f"  [bold green]V[/bold green] Added location #{idx}: "
                f"[cyan]lat={lat}[/cyan]  [cyan]lng={lng}[/cyan]  [dim]acc={acc}[/dim]"
            )

    finally:
        console.print("\n  [cyan]> [/cyan]Location config done, closing the map...")
        try:
            map_page.close()
        except Exception:
            pass

    if not locations:
        console.print(
            "  [bold red]X[/bold red] No locations configured. "
            "The check-in tool will not work without at least one location."
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
        "Configure Check-in Time Window",
        "Set the daily time range and scan frequency. "
        "The program will auto-detect and check in within this window."
    )

    console.print("  [dim]Current settings:[/dim]")
    console.print(f"    Start: [cyan]{window['schedule_window_start']}[/cyan]")
    console.print(f"    End:   [cyan]{window['schedule_window_end']}[/cyan]")
    console.print(f"    Interval: [cyan]{window['schedule_interval']}[/cyan] min\n")

    if not questionary.confirm("Modify the check-in window?", default=False).ask():
        return window

    start_str = ""
    while not start_str:
        start_str = prompt_input(
            "  Window start time (HH:MM, e.g. 20:00): ",
            default=window["schedule_window_start"]
        ).strip()
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', start_str):
            console.print("  [bold red]X[/bold red] Invalid format! Examples: 08:00, 20:00, 22:30")
            start_str = ""

    end_str = ""
    while not end_str:
        end_str = prompt_input(
            "  Window end time (HH:MM, e.g. 23:30): ",
            default=window["schedule_window_end"]
        ).strip()
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', end_str):
            console.print("  [bold red]X[/bold red] Invalid format! Examples: 08:00, 20:00, 22:30")
            end_str = ""

    interval_str = ""
    while not interval_str:
        interval_str = prompt_input(
            "  Scan interval (minutes): ",
            default=str(window["schedule_interval"])
        ).strip()
        if not re.match(r'^\d+$', interval_str) or int(interval_str) < 1:
            console.print("  [bold red]X[/bold red] Enter a positive integer (e.g. 5, 10, 15)")
            interval_str = ""

    window["schedule_window_start"] = start_str
    window["schedule_window_end"]   = end_str
    window["schedule_interval"]     = int(interval_str)

    console.print(
        f"\n  [bold green]V[/bold green] Check-in window set: "
        f"[cyan]{start_str}[/cyan] -> [cyan]{end_str}[/cyan], "
        f"scan every [bold]{interval_str}[/bold] min"
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
    console.rule("[bold yellow]Config Summary[/bold yellow]")

    table = Table(box=box.ROUNDED, border_style="dim", show_header=False, padding=(0, 1))
    table.add_column("Item", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Class IDs", ", ".join(config["classes"]) if config["classes"] else "[red]Not configured[/red]")
    table.add_row("Locations", f"{len(config['locations'])}")
    table.add_row("Accounts", f"{len(config['cookies'])}")

    if config.get("schedule_window_start") and config.get("schedule_window_end"):
        window = f"{config['schedule_window_start']} -> {config['schedule_window_end']}"
        table.add_row("Check-in window", f"[cyan]{window}[/cyan]  every [bold]{config.get('schedule_interval', 5)}[/bold] min")
    elif config.get("scheduletimes"):
        table.add_row("Times", "[cyan]" + "  /  ".join(config["scheduletimes"]) + "[/cyan]")
    else:
        table.add_row("Check-in window", "[yellow]Not set (immediate mode)[/yellow]")

    table.add_row("Debug mode", "[yellow]On[/yellow]" if config["debug"] else "[dim]Off[/dim]")

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
            "[bold white]ClassMagic GPS Auto Check-in -- Config Wizard[/bold white]\n"
            "[dim]Project: https://github.com/Moeus/AutoCheckBJMF[/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()

    existing = load_existing_config()
    if existing:
        console.print(
            Panel(
                "[yellow]Existing config found. Changes will be made on top of it.[/yellow]",
                border_style="yellow",
                padding=(0, 2),
            )
        )
        if questionary.confirm("Clear existing config and start fresh?", default=False).ask():
            existing = {}
            console.print(
                Panel(
                    "[red]Existing config cleared. Starting fresh.[/red]",
                    border_style="red",
                    padding=(0, 2),
                )
            )
    else:
        console.print("[dim]No existing config found, creating a new one.[/dim]\n")

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
    console.rule("[dim]Other settings[/dim]")
    debug = questionary.confirm(
        "Enable debug mode? (detailed logs written to AutoCheckBJMF.log)",
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

    if questionary.confirm("Save the above config?", default=True).ask():
        save_config(config)
        console.print(
            Panel(
                "[bold green]  Setup complete![/bold green]\n\n"
                "  [cyan]python main.py[/cyan]   -- start scheduled auto check-in\n"
                "  [cyan]python once.py[/cyan]   -- run one check-in immediately (emergency)",
                border_style="green",
                padding=(1, 4),
            )
        )
    else:
        console.print("[yellow]Cancelled, config not saved.[/yellow]")


if __name__ == "__main__":
    main()
