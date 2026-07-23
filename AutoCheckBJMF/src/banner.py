"""
Shared ASCII banner for AutoCheckBJMF.
"""

from rich.console import Console

console = Console()

_ASCII_ART = r"""
                 _                _____   _                     _        ____         _   __  __   ______ 
 /\             | |              / ____| | |                   | |      |  _ \       | | |  \/  | |  ____|
/  \     _   _  | |_    ___     | |      | |__     ___    ___  | | __   | |_) |      | | | \  / | | |__   
/ /\ \   | | | | | __|  / _ \    | |      | '_ \   / _ \  / __| | |/ /   |  _ <   _   | | | |\/| | |  __|  
/ ____ \  | |_| | | |_  | (_) |   | |____  | | | | |  __/ | (__  |   <    | |_) | | |__| | | |  | | | |     
/_/    \_\  \__,_|  \__|  \___/     \_____| |_| |_|  \___|  \___| |_|\_\   |____/   \____/  |_|  |_| |_|     
                                                                                                          
                                                                                                          
"""

def print_banner():
    """Print the rich-styled welcome banner with ASCII art title."""
    console.print(f"\n[bold cyan]{_ASCII_ART}[/bold cyan]")
    console.print()
