import datetime
import re

VERSION_FILE = "version.py"


def update_version():
    try:
        with open(VERSION_FILE, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = '__version__ = "v2026.6.11"\n'

    # Extract current version
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        current_version = "v2026.6.11"
    else:
        current_version = match.group(1)

    # Get today's date (no leading zeros for month and day)
    now = datetime.datetime.now()
    today_base = f"v{now.year}.{now.month}.{now.day}"

    # Check if current_version matches today's base
    if current_version.startswith(today_base):
        if current_version == today_base:
            new_version = f"{today_base}.1"
        else:
            suffix = current_version[len(today_base) :]
            if suffix.startswith("."):
                try:
                    counter = int(suffix[1:])
                    new_version = f"{today_base}.{counter + 1}"
                except ValueError:
                    new_version = f"{today_base}.1"
            else:
                new_version = f"{today_base}.1"
    else:
        # It's a new day!
        new_version = today_base

    # Replace version in file
    new_content = re.sub(
        r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"', content
    )

    with open(VERSION_FILE, "w") as f:
        f.write(new_content)

    print(f"📦 Version updated: {current_version} ➔ {new_version}")


if __name__ == "__main__":
    update_version()
