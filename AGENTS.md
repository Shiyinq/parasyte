# Parasyte — Agent Guide

## Lint & test
```bash
make lint           # autoflake + isort + black (auto-installs tools on first run)
.venv/bin/python test_verify.py
```
Tests: sel assignment logic, polyglot roundtrip, raw roundtrip, wrong-password rejection.

## CLI commands
- `infect` — encrypt: `--dna <file|folder>` (required), `--sel <path>` (default `sel/`), `--raw` (skip sel, output `.psyt`), `--shred`, `--chromosome` (zip before encrypt)
- `cure` — decrypt: `--host <file|folder>` (required), `--hive <path>` (default `<host>/cured/`), `--helicase` (unzip after decrypt)
- `update` — self-update from GitHub Releases

## Source files
- `parasyte.py` — CLI entry, argparse, rich UI, orchestration
- `core.py` — AES-256-GCM, PBKDF2, polyglot construction/extraction, file discovery, shred
- `test_verify.py` — test suite
- `version.py` — single `__version__ = "v..."` (bumped by `update_version.py`)

## Architecture
- **Encryption**: `_encrypt_payload()` in `core.py` handles all crypto — AES-256-GCM, PBKDF2 (600K iter), random salt/nonce. Encrypted blob = `[8B signature][12B nonce][16B tag][ciphertext][16B salt]`. Original filename is stored inside ciphertext (first 2B = length, then filename, then data).
- **Polyglot mode**: `build_polyglot()` prepends media data before payload. JPEG: cut at `FF D9`, PNG: cut at `IEND`, others: entire file + append.
- **Raw mode** (`--raw`): `build_raw_payload()` returns just the encrypted blob. Output filename = `os.urandom(6).hex() + ".psyt"` (random, 12 chars, no info leak).
- **Decrypt**: `cure_and_extract()` searches `rfind` for key-derived signature — works identically on polyglot and raw files.
- `infect_single()` is the unified encrypt function — `sel_path: Optional[str] = None`. If `sel_path` given → build polyglot; else → build raw .psyt.
- `cure --host folder/` auto-detects both media files (`.jpg`, `.png`, `.mp4`, `.mkv`, `.mp3`, `.wav`) and `.psyt` files via `collect_polyglot_files()`.

## Python 3.9 quirk
`str | None` type syntax fails. Use `Optional[str]` from `typing` instead.

## Build & release
- `make build` — Nuitka compile to standalone binary (`dist/parasyte.dist/`)
- `make install-parasyte` — symlink to `/usr/local/bin/parasyte`
- CI: GitHub Actions on tag push `v*`, builds macOS + Ubuntu binaries via Nuitka, uploads to release

## Conventions
- All file I/O in binary mode (`"rb"`/`"wb"`)
- Everything processed in-memory (no streaming)
- Dirs `dna/`, `sel/`, `hive/` are gitignored
