"""
Parasyte — AES-256-GCM Encryption + Media Polyglot

Encrypt any file and embed the encrypted data inside a media file
(JPEG, MP4, MKV) using the polyglot technique.
"""

import argparse
import hashlib
import os
import sys
import subprocess
import shutil
import zipfile
from typing import Optional

from version import __version__ as VERSION
from core import (
    DEFAULT_SEL_DIR,
    DEFAULT_HIVE_DIR,
    build_polyglot,
    build_raw_payload,
    cure_and_extract,
    secure_shred,
    collect_sel_files,
    collect_dna_files,
    collect_polyglot_files,
    assign_sel_files,
    detect_sel_type,
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
    hive_dir: str,
    password: str,
    sel_path: Optional[str] = None,
    shred: bool = False,
) -> tuple[bool, str]:
    """Encrypt a single DNA file. If sel_path given, embed in media; else raw .psyt."""
    try:
        dna_name = os.path.basename(dna_path)
        original_size = os.path.getsize(dna_path)

        with open(dna_path, "rb") as f:
            dna_data = f.read()

        if sel_path:
            with open(sel_path, "rb") as f:
                sel_data = f.read()
            payload = build_polyglot(sel_data, sel_path, dna_name, dna_data, password)
            output_filename = os.path.basename(sel_path)
        else:
            payload = build_raw_payload(dna_name, dna_data, password)
            output_filename = os.urandom(6).hex() + ".psyt"

        output_path = os.path.join(hive_dir, output_filename)

        if os.path.exists(output_path):
            name, ext = os.path.splitext(output_filename)
            counter = 1
            while os.path.exists(output_path):
                output_filename = f"{name}_{counter}{ext}"
                output_path = os.path.join(hive_dir, output_filename)
                counter += 1

        os.makedirs(hive_dir, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(payload)

        if shred:
            secure_shred(dna_path)

        msg = f"{dna_name} -> {output_filename} ({original_size:,} -> {len(payload):,} bytes)"
        return True, msg

    except Exception as e:
        return False, f"{os.path.basename(dna_path)}: {str(e)}"


def cure_single(
    polyglot_path: str,
    hive_dir: str,
    password: str,
    helicase: bool = False,
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
        name, ext = os.path.splitext(original_filename)

        if os.path.exists(output_path):
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(hive_dir, f"{name}_{counter}{ext}")
                counter += 1

        os.makedirs(hive_dir, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(decrypted_data)

        msg_suffix = ""
        if helicase and zipfile.is_zipfile(output_path):
            extract_dir = os.path.join(hive_dir, name)
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(output_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            os.remove(output_path)
            msg_suffix = f" (unzipped to '{name}/')"

        short_hash = hashlib.sha256(decrypted_data).hexdigest()[:6]
        msg = f"{polyglot_name} -> {original_filename} (sha256:{short_hash}){msg_suffix}"
        return True, msg

    except (ValueError, KeyError):
        return False, f"{os.path.basename(polyglot_path)}: Wrong password or corrupted data"
    except Exception as e:
        return False, f"{os.path.basename(polyglot_path)}: {str(e)}"


def cmd_infect(args):
    tmp_dir = None
    try:
        dna_path = args.dna
        if args.chromosome:
            tmp_dir = os.path.join(os.getcwd(), "tmp_parasyte_zip")
            os.makedirs(tmp_dir, exist_ok=True)
            if RICH_AVAILABLE:
                console.print(f"[yellow]Zipping target '{dna_path}'...[/yellow]")
            else:
                print(f"Zipping target '{dna_path}'...")
            base_name = os.path.join(tmp_dir, os.path.basename(os.path.normpath(dna_path)))
            
            if os.path.isdir(dna_path):
                shutil.make_archive(base_name, 'zip', dna_path)
                dna_path = base_name + ".zip"
            else:
                dna_path = base_name + ".zip"
                with zipfile.ZipFile(dna_path, 'w') as zf:
                    zf.write(args.dna, arcname=os.path.basename(args.dna))
                    
        dna_files = collect_dna_files(dna_path)
        if not args.raw:
            sel_files = collect_sel_files(args.sel)
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            print(f"Error: {e}")
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        sys.exit(1)

    hive_dir = args.hive

    table = Table(title="Infection Plan", title_justify="left", box=box.SIMPLE, show_header=False)
    table.add_row("DNA Payload", f"{len(dna_files)} file(s) from '{args.dna}'")
    if args.raw:
        table.add_row("Mode", "Raw Binary (.psyt)")
    else:
        table.add_row("Sels", f"{len(sel_files)} file(s) from '{args.sel}'")
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

    if not args.raw:
        assigned_sel_files = assign_sel_files(dna_files, sel_files)

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
        
        for idx, dna_file in enumerate(dna_files):
            if args.raw:
                success, msg = infect_single(dna_file, hive_dir, password, shred=args.shred)
            else:
                success, msg = infect_single(dna_file, hive_dir, password, sel_path=assigned_sel_files[idx], shred=args.shred)
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
    console.print(f"To cure: [bold cyan]{CMD_PREFIX} cure --host {hive_dir}[/bold cyan]")
    
    if tmp_dir and os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)


def cmd_cure(args):
    try:
        polyglot_files = collect_polyglot_files(args.host)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    input_path = args.host
    if args.hive:
        hive_dir = args.hive
    else:
        if os.path.isdir(input_path):
            hive_dir = os.path.join(input_path, "cured")
        else:
            hive_dir = os.path.join(os.path.dirname(input_path) or ".", "cured")

    table = Table(title="Curing Plan", title_justify="left", box=box.SIMPLE, show_header=False)
    table.add_row("Infected Files", f"{len(polyglot_files)} file(s) from '{args.host}'")
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
            success, msg = cure_single(poly_file, hive_dir, password, helicase=args.helicase)
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


def cmd_update(args):
    if not RICH_AVAILABLE:
        print("Checking for updates on GitHub...")
    else:
        console.print("[yellow]Checking for updates on GitHub...[/yellow]")
        
    try:
        # Use curl to get the latest tag from the redirect Location header
        cmd_latest = "curl -sI https://github.com/Shiyinq/parasyte/releases/latest | grep -i '^location:' | sed -E 's/.*\\/tag\\/([^[:space:]\\r]*).*/\\1/'"
        result = subprocess.run(cmd_latest, shell=True, capture_output=True, text=True)
        latest_tag = result.stdout.strip()
        
        if not latest_tag:
            msg = "Error: Could not determine the latest version from GitHub."
            if RICH_AVAILABLE:
                console.print(f"[red]{msg}[/red]")
            else:
                print(msg)
            sys.exit(1)
            
        if latest_tag == VERSION:
            msg = f"You are already using the latest version ({VERSION})."
            if RICH_AVAILABLE:
                console.print(f"[green]{msg}[/green]")
            else:
                print(msg)
            sys.exit(0)
        else:
            if RICH_AVAILABLE:
                console.print(f"[green]Update found![/green] {VERSION} -> {latest_tag}")
                console.print("Running automated install script (this may require sudo password)...")
            else:
                print(f"Update found! {VERSION} -> {latest_tag}")
                print("Running automated install script (this may require sudo password)...")
            
            # Execute the bash script
            install_cmd = "curl -fsSL https://raw.githubusercontent.com/Shiyinq/parasyte/main/install.sh | bash"
            subprocess.run(install_cmd, shell=True)
            
            release_url = f"https://github.com/Shiyinq/parasyte/releases/tag/{latest_tag}"
            if RICH_AVAILABLE:
                console.print(f"\n[bold cyan]✨ Update complete![/bold cyan]")
                console.print(f"View what's new in {latest_tag}: [link={release_url}]{release_url}[/link]")
            else:
                print(f"\n✨ Update complete!")
                print(f"View what's new in {latest_tag}: {release_url}")
            
    except Exception as e:
        msg = f"Failed to check for updates: {e}"
        if RICH_AVAILABLE:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        sys.exit(1)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    # Only add these if we don't have them imported (to avoid duplicate defaults if core is missing)
    try:
        from core import DEFAULT_SEL_DIR, DEFAULT_HIVE_DIR
    except ImportError:
        DEFAULT_SEL_DIR = "sel_files"
        DEFAULT_HIVE_DIR = "hive"

    parser = argparse.ArgumentParser(
        prog="parasyte",
        description="🦠 Parasyte — Encrypt files & hide them inside media",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {CMD_PREFIX} infect --dna secret.png
  {CMD_PREFIX} cure --host hive/
        """,
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    infect_parser = subparsers.add_parser("infect", help="Infect sel media with encrypted DNA payload")
    infect_parser.add_argument("--dna", required=True, help="DNA payload (file or folder)")
    infect_parser.add_argument("--sel", default=DEFAULT_SEL_DIR, help=f"Sel folder (default: {DEFAULT_SEL_DIR}/)")
    infect_parser.add_argument("--hive", default=DEFAULT_HIVE_DIR, help=f"Output folder (default: {DEFAULT_HIVE_DIR}/)")
    infect_parser.add_argument("--shred", action="store_true", help="Securely destroy original DNA files")
    infect_parser.add_argument("--chromosome", action="store_true", help="Condense (zip) the DNA folder/file before encrypting")
    infect_parser.add_argument("--raw", action="store_true", help="Encrypt to raw .psyt binary (no media disguise)")

    cure_parser = subparsers.add_parser("cure", help="Cure infected files to extract original DNA")
    cure_parser.add_argument("--host", required=True, help="Infected file or folder (Host)")
    cure_parser.add_argument("--hive", default=None, help="Output folder (default: <input_path>/cured/)")
    cure_parser.add_argument("--helicase", action="store_true", help="Unwind (unzip) extracted payload if it's a valid condensed chromosome (ZIP)")

    update_parser = subparsers.add_parser("update", help="Update Parasyte to the latest version directly from GitHub")

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
    elif args.command == "update":
        cmd_update(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        if RICH_AVAILABLE:
            console.print("\n[bold red]Cancelled.[/bold red]")
        else:
            print("\nCancelled.")
        sys.exit(130)
