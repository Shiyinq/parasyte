# 🦠 Parasyte

**Encrypt any file and hide it inside innocent-looking media files.**

Parasyte uses **AES-256-GCM encryption** combined with the **polyglot file technique** to embed encrypted data inside images (JPEG, PNG) and audio/video media (MP4, MKV, MP3, WAV). The output files look and behave completely normal — they open in image viewers and media players — but contain your secret data, recoverable only with the correct password.

---

## Table of Contents

- [Terminology](#terminology)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Infect (Encrypt)](#infect-encrypt)
  - [Cure (Decrypt)](#cure-decrypt)
- [Examples](#examples)
- [Project Structure](#project-structure)
- [Security Details](#security-details)
- [Limitations](#limitations)
- [Running Tests](#running-tests)

---

## Terminology

To embrace the biological Sci-Fi theme, this CLI uses specialized terms instead of boring standard cryptographic words. Here is your survival guide:

| Term | Technical Meaning | Description |
|---|---|---|
| **`infect`** | **Encrypt** | The command to encrypt your secret data and inject it into a media file. |
| **`cure`** | **Decrypt** | The command to extract and decrypt your data back from an infected file. |
| **`--dna`** | **Payload / Data** | Your secret files (the "genetic code" of the parasite) that you want to hide. |
| **`--carrier`** | **Carrier / Host** | The innocent-looking media file (image, video, audio) that will act as the host. |
| **`--hive`** | **Output Directory** | The folder where the resulting infected (or cured) files will be saved. |
| **`--shred`** | **Secure Delete** | Permanently and securely wipes the original DNA file from your hard drive after a successful infection. |

---

## How It Works

### The Polyglot Technique

A **polyglot file** is a single file that is valid in two or more formats simultaneously. Parasyte exploits how media formats handle their data boundaries:

- **JPEG / PNG** files have specific end markers (`FF D9` for JPEG, `IEND` for PNG). Image viewers stop reading after this marker and ignore anything that follows.
- **Audio / Video** files (MP4, MKV, MP3, WAV) use container structures or frame formats. Players only read the declared structure/duration and ignore trailing data.

Parasyte appends encrypted data **after** these boundaries. The result is a file that:
- ✅ Opens normally in image viewers / video players
- ✅ Passes basic file format validation
- ✅ Contains your encrypted secret data

### Encryption Flow

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────────────────┐
│  Your Secret    │     │   Password   │     │      Carrier File            │
│  (any file)     │     │              │     │  (JPEG/PNG/MP4/MKV/MP3/WAV)  │
└────────┬────────┘     └──────┬───────┘     └──────────────┬───────────────┘
         │                     │                            │
         ▼                     ▼                            │
   Read as binary      PBKDF2 (600K iterations)             │
         │              + random salt                       │
         │                     │                            │
         │                     ▼                            │
         │              256-bit AES key                     │
         │                     │                            │
         ▼                     ▼                            ▼
   ┌───────────────────────────────────┐    ┌───────────────────────────┐
   │  AES-256-GCM Encrypt             │    │  Find media boundary      │
   │  → ciphertext + auth tag         │    │  (JPEG/PNG: after end tag)│
   └──────────────┬────────────────────┘    │  (Audio/Video: end of file│
                  │                         └─────────────┬─────────────┘
                  ▼                                       │
   ┌──────────────────────────────┐                       │
   │  Build Payload:              │                       │
   │  Key-Derived Signature (8B)  │                       │
   │  + filename + nonce + tag    │                       │
   │  + ciphertext + salt         │                       │
   └──────────────┬───────────────┘                       │
                  │                                       │
                  ▼                                       ▼
            ┌─────────────────────────────────────────────────┐
            │  Carrier media data  +  Encrypted payload       │
            │  (looks normal)         (invisible to viewers)  │
            └─────────────────────────────────────────────────┘
                                    │
                                    ▼
                           Output polyglot file
                      (opens normally as image/video)
```

### Decryption Flow

```
Polyglot file  →  Find 16-byte salt at end of file
                                                    │
                                    Password + PBKDF2 → AES key
                                                    │
                                     Generate expected signature
                                                    │
                                         Find payload boundary
                                                    │
                                          ┌─────────┴─────────┐
                                          │  nonce + tag      │
                                          │  + ciphertext     │
                                          └─────────┬─────────┘
                                                    │
                                            AES-256-GCM Decrypt
                                                    │
                                            Original file restored
                                          (byte-for-byte identical)
```

### File Structure

```
┌─────────────────────────────────────┐
│  Original Media Data                │  ← Image viewer / video player reads this
│  (JPEG/PNG: up to end markers)     │
│  (Audio/Video: full container)     │
├─────────────────────────────────────┤
│  Signature    (8 bytes)            │  ← Key-derived random signature
│  Filename Len (2 bytes, big-endian) │  ← Original filename length
│  Filename     (N bytes, UTF-8)     │  ← Original filename preserved
│  Nonce        (12 bytes)           │  ← AES-GCM random nonce
│  Auth Tag     (16 bytes)           │  ← AES-GCM authentication tag
│  Ciphertext   (variable)          │  ← Encrypted file data
│  Salt         (16 bytes)           │  ← PBKDF2 random salt (at the very end)
└─────────────────────────────────────┘
```

---

## Installation

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
# Clone or navigate to the project
cd parasyte

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install pycryptodome
```

**That's it.** Only one external dependency (`pycryptodome`).

### Standalone Binary Installation (Optional)

If you want to compile Parasyte into a single standalone executable (so you can run it anywhere natively without Python), you can use the provided Makefile:

```bash
make install
make build
```

This will generate a standalone binary at `dist/parasyte`. You can then install it globally to your system:
```bash
sudo mv ./dist/parasyte /usr/local/bin/
```

---

## Quick Start

```bash
# 1. Put carrier files (JPEG/PNG/MP4/MKV/MP3/WAV) in the carriers/ folder
#    These are the "disguise" files — your secret will be hidden inside them.

# 2. Infect a carrier
python parasyte.py infect --dna dna/example.png
# → Enter password (hidden input)
# → Output: hive/example.png  (assuming the carrier assigned was example.png)

# 3. The output file looks like a normal image/video!
open hive/example.png   # Opens in Preview

# 4. Cure it back
python parasyte.py cure --input hive/example.png
# → Enter password
# → Output: hive/cured/example.png  (identical to the original)
```

---

## Usage

### Infect (Encrypt)

```bash
python parasyte.py infect --dna <file_or_folder> [--carrier <carrier_path>] [--hive <output_path>] [--shred]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--dna` | ✅ | — | DNA Payload (file or folder to hide). If folder, all files inside are infected recursively. |
| `--carrier` | ❌ | `carriers/` | Path to carrier files. A random carrier is assigned to each DNA file. |
| `--hive` | ❌ | `hive/` | Output folder for infected polyglot files. |
| `--shred` | ❌ | `False` | Securely destroy the original DNA file with random bytes after successful infection. |

**Carrier assignment rules:**
- Each DNA file is randomly assigned a carrier (never sequential).
- If there are more carriers than DNA files, each DNA file gets a unique carrier.
- If there are fewer carriers than DNA files, some carriers are reused.

### Cure (Decrypt)

```bash
python parasyte.py cure --input <file_or_folder> [--hive <output_path>]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--input` | ✅ | — | Infected polyglot file or folder to cure. If folder, all media files inside are cured recursively. |
| `--hive` | ❌ | `<input>/cured/` | Output folder for cured files. Files are restored with their original DNA filenames. |

---

## Examples

### Encrypt a single file

```bash
python parasyte.py infect --dna dna/example.png
```

Output:
```text
  Infection Plan

  DNA Payload   1 file(s) from 'dna/example.png'
  Carriers      3 file(s) from 'carriers/'
  Hive Output   hive
  Encryption    AES-256-GCM (PBKDF2 600,000 iterations)

Enter password:
Confirm password:

Infecting...
[ SUCCESS ] example.png -> example.png (2,048,000 -> 2,325,085 bytes)
Processing... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

Done: 1/1 file(s) infected successfully
Output directory: /path/to/hive
To cure: python parasyte.py cure --input hive
```

### Infect an entire folder

```bash
python parasyte.py infect \
  --dna ./secret_documents/ \
  --carrier /Volumes/USB/carriers/ \
  --hive /Volumes/USB/hive/
```

Output:
```text
  Infection Plan

  DNA Payload   5 file(s) from './secret_documents/'
  Carriers      3 file(s) from '/Volumes/USB/carriers/'
  Hive Output   /Volumes/USB/hive/
  Encryption    AES-256-GCM (PBKDF2 600,000 iterations)

Enter password:
Confirm password:

Infecting...
[ SUCCESS ] contract.pdf -> vacation.mp4 (1,200,000 -> 3,400,000 bytes)
[ SUCCESS ] id_card.jpg -> sunset.jpeg (500,000 -> 1,200,000 bytes)
[ SUCCESS ] tax_return.pdf -> cat_video.mkv (2,000,000 -> 8,500,000 bytes)
[ SUCCESS ] bank_stmt.pdf -> sunset_1.jpeg (300,000 -> 1,000,000 bytes)
[ SUCCESS ] medical.pdf -> vacation_1.mp4 (800,000 -> 3,000,000 bytes)
Processing... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:02

Done: 5/5 file(s) infected successfully
Output directory: /Volumes/USB/hive/
To cure: python parasyte.py cure --input /Volumes/USB/hive/
```

### Cure an entire hive

```bash
python parasyte.py cure --input /Volumes/USB/hive/
```

Output:
```text
  Curing Plan

  Infected Files   5 file(s) from '/Volumes/USB/hive/'
  Output Directory /Volumes/USB/hive/cured

Enter password:

Curing...
[ SUCCESS ] vacation.mp4 -> contract.pdf (sha256:a1b2c3)
[ SUCCESS ] sunset.jpeg -> id_card.jpg (sha256:d4e5f6)
...
Processing... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:02

Done: 5/5 file(s) cured successfully
Cured output at: /Volumes/USB/hive/cured
```

### Cure to a specific folder

```bash
python parasyte.py cure --input hive/ --hive ~/Desktop/cured_data/
```

---

## Project Structure

```
parasyte/
├── parasyte.py          # Main CLI application
├── test_verify.py       # Automated verification tests
├── README.md            # This file
├── carriers/            # Carrier files (your "disguise" media)
│   ├── example.png      # Any image (JPEG, PNG)
│   ├── video.mp4        # Any video (MP4, MKV)
│   └── audio.mp3        # Any audio (MP3, WAV)
├── dna/                 # Files to encrypt (your secrets)
│   └── example.png
└── hive/                # Encrypted output (polyglot files)
    └── example.png
```

---

## Security Details

| Component | Specification |
|-----------|--------------|
| **Encryption** | AES-256-GCM (authenticated encryption) |
| **Key Derivation** | PBKDF2 with 600,000 iterations |
| **Hash Function** | SHA-256 (for PBKDF2 HMAC & Signature) |
| **Salt** | 16 bytes, cryptographically random (stored at end of file) |
| **Nonce** | 12 bytes, cryptographically random (unique per file) |
| **Auth Tag** | 16 bytes (provided by GCM mode) |
| **Signature** | 8 bytes, derived from AES key using SHA-256 |
| **Library** | PyCryptodome |

### What AES-GCM provides:

- **Confidentiality** — data is unreadable without the key
- **Integrity** — any modification to the ciphertext is detected
- **Authenticity** — guarantees the data was encrypted with the correct key

### What happens with a wrong password:

The decryption **fails completely** with an error. It does **not** produce corrupted or partial output. This is a key advantage of authenticated encryption (GCM mode) over simpler modes like CBC.

---

## Limitations

### Social Media Re-encoding

Most social media platforms **re-encode** uploaded images and videos. This process creates a brand new file from pixel/frame data, which **destroys** the hidden payload.

| Platform | Survives upload? |
|----------|:---------------:|
| Instagram | ❌ |
| Facebook | ❌ |
| Twitter/X | ❌ |
| WhatsApp (as photo) | ❌ |
| Telegram (as file/document) | ✅ |
| WhatsApp (as document) | ✅ |
| Google Drive | ✅ |
| Dropbox | ✅ |
| Email attachment | ✅ |
| USB / direct transfer | ✅ |

**Rule of thumb:** As long as the file is transferred as-is (not re-encoded), the hidden data survives.

### File Size

The output file size = carrier size + encrypted data size + small overhead (~50 bytes).

If your secret file is much larger than the carrier, the output file will be noticeably larger. For example, a 200 KB JPEG carrier containing a 500 MB video will produce a ~500 MB "image" — which may look suspicious.

### Memory Usage

The current implementation loads entire files into memory. For very large files (>1 GB), this may require significant RAM.

---

## Running Tests

```bash
source .venv/bin/activate
python test_verify.py
```

The test suite verifies:
1. **Carrier assignment logic** — unique assignment, reuse, and randomness
2. **Encrypt/decrypt roundtrip** — every data file × every carrier format
3. **Data integrity** — byte-for-byte comparison via SHA-256
4. **Wrong password rejection** — ensures wrong passwords are detected
5. **File format validity** — output files have correct media headers

---

## License

MIT
