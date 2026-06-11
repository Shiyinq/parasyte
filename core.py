import hashlib
import os
import random
import struct

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

# ─── Constants ────────────────────────────────────────────────────────────────

SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
KDF_ITERATIONS = 600_000
KEY_SIZE = 32  # AES-256

DEFAULT_CARRIER_DIR = "carriers"
DEFAULT_HIVE_DIR = "hive"

JPEG_END_MARKER = b"\xff\xd9"

CARRIER_EXTENSIONS = {
    "jpeg": [".jpg", ".jpeg"],
    "png": [".png"],
    "mp4": [".mp4"],
    "mkv": [".mkv"],
    "mp3": [".mp3"],
    "wav": [".wav"],
}

ALL_CARRIER_EXTS = [ext for exts in CARRIER_EXTENSIONS.values() for ext in exts]


# ─── Crypto Helpers ──────────────────────────────────────────────────────────

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password using PBKDF2."""
    return PBKDF2(
        password.encode("utf-8"),
        salt,
        dkLen=KEY_SIZE,
        count=KDF_ITERATIONS,
        hmac_hash_module=SHA256,
    )


# ─── Polyglot Helpers ────────────────────────────────────────────────────────

def detect_carrier_type(filepath: str) -> str:
    """Detect carrier type from magic bytes first, fallback to file extension."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(12)
        if header.startswith(b"\xff\xd8"):
            return "jpeg"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
    except Exception:
        pass

    ext = os.path.splitext(filepath)[1].lower()
    for carrier_type, extensions in CARRIER_EXTENSIONS.items():
        if ext in extensions:
            return carrier_type
    raise ValueError(f"Unsupported carrier format: {ext}")


def is_carrier_file(filepath: str) -> bool:
    """Check if a file has a supported carrier extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in ALL_CARRIER_EXTS


def find_jpeg_end(data: bytes) -> int:
    """Find the position right after the last FF D9 marker in JPEG data."""
    pos = data.rfind(JPEG_END_MARKER)
    if pos == -1:
        raise ValueError("Not a valid JPEG file (FF D9 end marker not found)")
    return pos + 2


def find_png_end(data: bytes) -> int:
    """Find the position right after the IEND chunk in PNG data."""
    pos = data.rfind(b"\x00\x00\x00\x00IEND\xae\x42\x60\x82")
    if pos == -1:
        raise ValueError("Not a valid PNG file (IEND chunk not found)")
    return pos + 12


def build_polyglot(
    carrier_data: bytes,
    carrier_path: str,
    original_filename: str,
    original_data: bytes,
    password: str,
) -> bytes:
    """Build a polyglot media file."""
    carrier_type = detect_carrier_type(carrier_path)
    
    salt = get_random_bytes(SALT_SIZE)
    key = derive_key(password, salt)
    
    cipher = AES.new(key, AES.MODE_GCM, nonce=get_random_bytes(NONCE_SIZE))
    ciphertext, tag = cipher.encrypt_and_digest(original_data)
    
    signature = hashlib.sha256(key + b"PARASYTE_SIG").digest()[:8]
    
    filename_bytes = original_filename.encode("utf-8")
    filename_length = struct.pack(">H", len(filename_bytes))
    
    payload = signature + filename_length + filename_bytes + cipher.nonce + tag + ciphertext + salt

    if carrier_type == "jpeg":
        jpeg_end = find_jpeg_end(carrier_data)
        return carrier_data[:jpeg_end] + payload
    elif carrier_type == "png":
        png_end = find_png_end(carrier_data)
        return carrier_data[:png_end] + payload
    else:
        return carrier_data + payload


def cure_and_extract(polyglot_data: bytes, password: str) -> tuple[str, bytes]:
    """Extract hidden data from a polyglot media file and decrypt it."""
    if len(polyglot_data) < SALT_SIZE:
        raise ValueError("File is too small to contain hidden data")

    salt = polyglot_data[-SALT_SIZE:]
    key = derive_key(password, salt)
    expected_signature = hashlib.sha256(key + b"PARASYTE_SIG").digest()[:8]
    
    magic_pos = polyglot_data.rfind(expected_signature)
    if magic_pos == -1:
        raise ValueError("Key-derived signature mismatch")

    hidden = polyglot_data[magic_pos:]
    offset = 8  # Skip signature

    filename_length = struct.unpack(">H", hidden[offset : offset + 2])[0]
    offset += 2

    original_filename = hidden[offset : offset + filename_length].decode("utf-8")
    offset += filename_length

    nonce = hidden[offset : offset + NONCE_SIZE]
    offset += NONCE_SIZE

    tag = hidden[offset : offset + TAG_SIZE]
    offset += TAG_SIZE

    ciphertext = hidden[offset : -SALT_SIZE]

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)

    return original_filename, decrypted_data


# ─── File Operations ─────────────────────────────────────────────────────────

def secure_shred(filepath: str):
    """Securely overwrite file with random bytes before deleting."""
    try:
        size = os.path.getsize(filepath)
        with open(filepath, "r+b") as f:
            chunk_size = 64 * 1024
            for _ in range(0, size, chunk_size):
                f.write(os.urandom(min(chunk_size, size - f.tell())))
        os.remove(filepath)
    except Exception as e:
        raise RuntimeError(f"Failed to securely shred '{filepath}': {e}")


# ─── File Discovery ──────────────────────────────────────────────────────────

def collect_carriers(carrier_path: str) -> list[str]:
    """Collect all carrier files from a directory (recursive)."""
    if os.path.isfile(carrier_path):
        if is_carrier_file(carrier_path):
            return [os.path.abspath(carrier_path)]
        else:
            raise ValueError(f"File '{carrier_path}' is not a supported carrier format. Supported: {', '.join(ALL_CARRIER_EXTS)}")

    carriers = []
    for root, _, files in os.walk(carrier_path):
        for f in files:
            filepath = os.path.join(root, f)
            if is_carrier_file(filepath):
                carriers.append(os.path.abspath(filepath))

    if not carriers:
        raise FileNotFoundError(f"No carrier files found in '{carrier_path}'. Supported: {', '.join(ALL_CARRIER_EXTS)}")

    return sorted(carriers)


def collect_dna_files(dna_path: str) -> list[str]:
    """Collect all data (DNA) files to be encrypted from a directory."""
    if os.path.isfile(dna_path):
        return [os.path.abspath(dna_path)]

    if not os.path.isdir(dna_path):
        return []

    files = []
    for root, dirs, filenames in os.walk(dna_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for f in filenames:
            if not f.startswith("."):
                files.append(os.path.abspath(os.path.join(root, f)))

    if not files:
        raise FileNotFoundError(f"No files found in '{dna_path}'")

    return sorted(files)


def collect_polyglot_files(input_path: str) -> list[str]:
    """Collect polyglot files to decrypt."""
    if os.path.isfile(input_path):
        return [os.path.abspath(input_path)]

    if not os.path.isdir(input_path):
        raise FileNotFoundError(f"Path not found: {input_path}")

    files = []
    for root, dirs, filenames in os.walk(input_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in filenames:
            filepath = os.path.join(root, f)
            if is_carrier_file(filepath):
                files.append(os.path.abspath(filepath))

    if not files:
        raise FileNotFoundError(f"No media files found in '{input_path}'")

    return sorted(files)


def assign_carriers(data_files: list[str], carriers: list[str]) -> list[str]:
    """Assign a random carrier to each data file."""
    n_data = len(data_files)
    n_carriers = len(carriers)

    if n_data <= n_carriers:
        assigned = random.sample(carriers, n_data)
    else:
        assigned = list(carriers)
        remaining = n_data - n_carriers
        assigned.extend(random.choices(carriers, k=remaining))
        random.shuffle(assigned)

    return assigned
