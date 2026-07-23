"""
once.py -- AutoCheckBJMF one-shot check-in
==========================================
Emergency use: reads config.json, immediately signs in all classes/accounts,
then exits. No scheduling involved.

Usage:
    python once.py

If config.json is missing, run make_config.py first.
"""

from main import load_config, setup_logger, run_all_classes, console

from rich.panel import Panel
from rich.table import Table
from rich import box

from banner import print_banner


def main():
    """
    Entry point:
    1. Load config (shared with main.py)
    2. Init logger
    3. Immediately check in all classes/accounts
    4. Wait for user to press Enter before exit
    """
    print_banner()
    console.print(Panel(
        "[bold white]AutoCheckBJMF -- ClassMagic GPS Auto Check-in[/bold white]  [bold yellow]One-shot mode[/bold yellow]\n"
        "[dim]Project: https://github.com/Moeus/AutoCheckBJMF[/dim]\n"
        "[bold yellow]* Launches immediately, no scheduling[/bold yellow]",
        border_style="yellow", padding=(0, 4)
    ))

    cfg = load_config()
    classes   = cfg["classes"]
    locations = cfg["locations"]
    cookies   = cfg["cookies"]
    debug     = cfg.get("debug", False)

    logger = setup_logger(debug)

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Class IDs", ", ".join(classes) if classes else "[red]Not configured[/red]")
    table.add_row("Accounts", str(len(cookies)))
    table.add_row("Locations", str(len(locations)))
    table.add_row("Debug mode", "[yellow]On[/yellow]" if debug else "[dim]Off[/dim]")
    console.print(table)

    if not classes:
        console.print(Panel(
            "[bold red]X  No class IDs configured[/bold red]\n"
            "Please run [cyan]python make_config.py[/cyan] to configure.",
            border_style="red", padding=(0, 2)
        ))
        input("Press Enter to exit...")
        return

    if not cookies:
        console.print(Panel(
            "[bold red]X  No account cookies configured[/bold red]\n"
            "Please run [cyan]python make_config.py[/cyan] to configure.",
            border_style="red", padding=(0, 2)
        ))
        input("Press Enter to exit...")
        return

    if not locations:
        console.print(Panel(
            "[bold red]X  No GPS locations configured[/bold red]\n"
            "Please run [cyan]python make_config.py[/cyan] to configure.",
            border_style="red", padding=(0, 2)
        ))
        input("Press Enter to exit...")
        return

    run_all_classes(classes, cookies, locations, debug, logger)

    console.print(Panel(
        "[bold green]V  One-shot check-in complete.[/bold green]",
        border_style="green", padding=(0, 2)
    ))
    input("  Press Enter to close...")


if __name__ == "__main__":
    main()
