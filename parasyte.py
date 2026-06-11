"""
Parasyte — AES-256-GCM Encryption + Media Polyglot

Encrypt any file and embed the encrypted data inside a media file
(JPEG, MP4, MKV) using the polyglot technique.
"""

import argparse
import hashlib
import os
import sys

from version import __version__ as VERSION
from core import (
    DEFAULT_CARRIER_DIR,
    DEFAULT_HIVE_DIR,
    build_polyglot,
    cure_and_extract,
    secure_shred,
    collect_carriers,
    collect_dna_files,
    collect_polyglot_files,
    assign_carriers,
    detect_carrier_type,
)

# Optional rich import, with fallback if not installed yet
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.prompt import Prompt
    from rich import box
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' library not found. Please run 'pip install -r requirements.txt'")
    sys.exit(1)

# Dynamically determine how the script was invoked for accurate help messages
if sys.argv[0].endswith('.py'):
    CMD_PREFIX = f"python {os.path.basename(sys.argv[0])}"
else:
    CMD_PREFIX = os.path.basename(sys.argv[0])

# ─── Commands ────────────────────────────────────────────────────────────────

def infect_single(
    dna_path: str,
    carrier_path: str,
    hive_dir: str,
    password: str,
    shred: bool = False,
) -> tuple[bool, str]:
    """Infect a single carrier with the DNA payload."""
    try:
        dna_name = os.path.basename(dna_path)
        original_size = os.path.getsize(dna_path)

        with open(dna_path, "rb") as f:
            dna_data = f.read()

        with open(carrier_path, "rb") as f:
            carrier_data = f.read()

        polyglot = build_polyglot(carrier_data, carrier_path, dna_name, dna_data, password)

        carrier_name = os.path.basename(carrier_path)
        output_filename = carrier_name
        output_path = os.path.join(hive_dir, output_filename)

        if os.path.exists(output_path):
            name, ext = os.path.splitext(carrier_name)
            counter = 1
            while os.path.exists(output_path):
                output_filename = f"{name}_{counter}{ext}"
                output_path = os.path.join(hive_dir, output_filename)
                counter += 1

        os.makedirs(hive_dir, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(polyglot)

        if shred:
            secure_shred(dna_path)

        msg = f"{dna_name} -> {output_filename} ({original_size:,} -> {len(polyglot):,} bytes)"
        return True, msg

    except Exception as e:
        return False, f"{os.path.basename(dna_path)}: {str(e)}"


def cure_single(
    polyglot_path: str,
    hive_dir: str,
    password: str,
) -> tuple[bool, str]:
    """Extract and decrypt (cure) a single polyglot file."""
    try:
        polyglot_name = os.path.basename(polyglot_path)

        with open(polyglot_path, "rb") as f:
            polyglot_data = f.read()

        try:
            original_filename, decrypted_data = cure_and_extract(polyglot_data, password)
        except ValueError as e:
            if "Key-derived signature mismatch" in str(e):
                return False, f"Skipped {polyglot_name} (Not infected / Wrong password)"
            raise e

        output_path = os.path.join(hive_dir, original_filename)

        if os.path.exists(output_path):
            name, ext = os.path.splitext(original_filename)
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(hive_dir, f"{name}_{counter}{ext}")
                counter += 1

        os.makedirs(hive_dir, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(decrypted_data)

        short_hash = hashlib.sha256(decrypted_data).hexdigest()[:6]
        msg = f"{polyglot_name} -> {original_filename} (sha256:{short_hash})"
        return True, msg

    except (ValueError, KeyError):
        return False, f"{os.path.basename(polyglot_path)}: Wrong password or corrupted data"
    except Exception as e:
        return False, f"{os.path.basename(polyglot_path)}: {str(e)}"


def cmd_infect(args):
    try:
        dna_files = collect_dna_files(args.dna)
        carriers = collect_carriers(args.carrier)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    hive_dir = args.hive

    table = Table(title="Infection Plan", title_justify="left", box=box.SIMPLE, show_header=False)
    table.add_row("DNA Payload", f"{len(dna_files)} file(s) from '{args.dna}'")
    table.add_row("Carriers", f"{len(carriers)} file(s) from '{args.carrier}'")
    table.add_row("Hive Output", hive_dir)
    table.add_row("Encryption", "AES-256-GCM (PBKDF2 600,000 iterations)")
    
    console.print()
    console.print(table)
    console.print()

    password = Prompt.ask("Enter password", password=True)
    confirm = Prompt.ask("Confirm password", password=True)
    if password != confirm:
        console.print("[bold red]Error:[/bold red] Passwords do not match!")
        sys.exit(1)

    assigned_carriers = assign_carriers(dna_files, carriers)

    console.print("\n[bold]Infecting...[/bold]")
    
    success_count = 0
    total = len(dna_files)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Processing...", total=total)
        
        for dna_file, carrier_file in zip(dna_files, assigned_carriers):
            success, msg = infect_single(dna_file, carrier_file, hive_dir, password, args.shred)
            if success:
                success_count += 1
                progress.console.print(f"[green][ SUCCESS ][/green] {msg}", highlight=False)
            else:
                progress.console.print(f"[red][ ERROR ][/red] {msg}", highlight=False)
            progress.advance(task)

    console.print()
    if success_count == total:
        console.print(f"[bold green]Done:[/bold green] {success_count}/{total} file(s) infected successfully")
    else:
        console.print(f"[bold yellow]Done:[/bold yellow] {success_count}/{total} file(s) infected successfully")
    console.print(f"Output directory: {os.path.abspath(hive_dir)}")
    console.print(f"To cure: [bold cyan]{CMD_PREFIX} cure --input {hive_dir}[/bold cyan]")


def cmd_cure(args):
    try:
        polyglot_files = collect_polyglot_files(args.input)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    input_path = args.input
    if args.hive:
        hive_dir = args.hive
    else:
        if os.path.isdir(input_path):
            hive_dir = os.path.join(input_path, "cured")
        else:
            hive_dir = os.path.join(os.path.dirname(input_path) or ".", "cured")

    table = Table(title="Curing Plan", title_justify="left", box=box.SIMPLE, show_header=False)
    table.add_row("Infected Files", f"{len(polyglot_files)} file(s) from '{args.input}'")
    table.add_row("Output Directory", hive_dir)
    
    console.print()
    console.print(table)
    console.print()

    password = Prompt.ask("Enter password", password=True)

    console.print("\n[bold]Curing...[/bold]")
    
    success_count = 0
    total = len(polyglot_files)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Processing...", total=total)
        
        for poly_file in polyglot_files:
            success, msg = cure_single(poly_file, hive_dir, password)
            if success:
                success_count += 1
                progress.console.print(f"[green][ SUCCESS ][/green] {msg}", highlight=False)
            else:
                progress.console.print(f"[yellow][ SKIPPED/ERROR ][/yellow] {msg}", highlight=False)
            progress.advance(task)

    console.print()
    if success_count == total:
        console.print(f"[bold green]Done:[/bold green] {success_count}/{total} file(s) cured successfully")
    else:
        console.print(f"[bold yellow]Done:[/bold yellow] {success_count}/{total} file(s) cured successfully")
    console.print(f"Cured output at: {os.path.abspath(hive_dir)}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    # Only add these if we don't have them imported (to avoid duplicate defaults if core is missing)
    try:
        from core import DEFAULT_CARRIER_DIR, DEFAULT_HIVE_DIR
    except ImportError:
        DEFAULT_CARRIER_DIR = "carriers"
        DEFAULT_HIVE_DIR = "hive"

    parser = argparse.ArgumentParser(
        prog="parasyte",
        description="🦠 Parasyte — Encrypt files & hide them inside media",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {CMD_PREFIX} infect --dna secret.png
  {CMD_PREFIX} cure --input hive/
        """,
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    infect_parser = subparsers.add_parser("infect", help="Infect carrier media with encrypted DNA payload")
    infect_parser.add_argument("--dna", required=True, help="DNA payload (file or folder)")
    infect_parser.add_argument("--carrier", default=DEFAULT_CARRIER_DIR, help=f"Carrier folder (default: {DEFAULT_CARRIER_DIR}/)")
    infect_parser.add_argument("--hive", default=DEFAULT_HIVE_DIR, help=f"Output folder (default: {DEFAULT_HIVE_DIR}/)")
    infect_parser.add_argument("--shred", action="store_true", help="Securely destroy original DNA files")

    cure_parser = subparsers.add_parser("cure", help="Cure infected files to extract original DNA")
    cure_parser.add_argument("--input", required=True, help="Infected file or folder")
    cure_parser.add_argument("--hive", default=None, help="Output folder (default: <input_path>/cured/)")

    args = parser.parse_args()

    if args.command is None:
        if RICH_AVAILABLE:
            ascii_art = """[bold green]
▄  ▄▄▄▄▄▄    ▄▄▄▄▄▄    ▄  ▄▄▄▄▄▄     ▄▄▄▄▄▄        ▄▄▄▄▄  ▐█▌▌   ▐██▌    ▄▄▄▄▄▄▄▄    ▄▄▄▄▄▄        
▐█▌▀  ▀▀█▄ ▄▄█▀  ▀▀█▄  ▐█▌▀  ▀▀█▄  ▄▄█▀  ▀▀█▄    ▄▄▀ ▀▀█▀ ▐█▌▌   ▐██▌ ▄▄█▀ ██  ▀█▄ ▄▄█▀  ▀▀█▄      
▐██▌  ▄▄█▌ ▐█▌    ▐▐█▌ ▐██▌   ▄█▌  ▐█▌    ▐▐█▌   ██▄▄     ▐██▄▄  ▐██▌  █▀ ▐▐█▌     ▐█▌    ▐▐█▌     
▐██▌▀▀▀▀▀  ▐█▌▀▀▀▀▀██▌ ▐██▌▀▀▀▄▄▄  ▐█▌▀▀▀▀▀██▌   ▀▀▀████▄  ▀▀▀▀▀▀▀██▌      ▐██     ▐██▀▀▀▀         
 ▐█▌       ▐█▌    ▐██▌  ▐█▌    ██▌ ▐█▌    ▐██▌ ▄▄     ▀▀█ ▐█▌    ▄██▌      ▐██     ███     ██      
 ▐██▌      ▐█▌    ▐██▌  ▐██▌  ▐█▌  ▐█▌    ▐██▌ ▐██▄▄▄▄▄▀   ▀█▄▄▄▄██▀       ▐██      ▀▀█▄▄▄█▀       
                                                ▀▀▀▀                                               
[/bold green]"""
            console.print(ascii_art, highlight=False)
            console.print()
            # https://patorjk.com/software/taag/#p=display&f=VisionX+Gree&t=Parasyte+&x=none&v=4&h=4&w=80&we=false&ft=thedraw
        parser.print_help()
        sys.exit(0)

    if args.command == "infect":
        cmd_infect(args)
    elif args.command == "cure":
        cmd_cure(args)


if __name__ == "__main__":
    main()
