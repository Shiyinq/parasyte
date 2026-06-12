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

DEFAULT_SEL_DIR = "sel"
DEFAULT_HIVE_DIR = "hive"

JPEG_END_MARKER = b"\xff\xd9"

SEL_EXTENSIONS = {
    "jpeg": [".jpg", ".jpeg"],
    "png": [".png"],
    "mp4": [".mp4"],
    "mkv": [".mkv"],
    "mp3": [".mp3"],
    "wav": [".wav"],
}

ALL_SEL_EXTS = [ext for exts in SEL_EXTENSIONS.values() for ext in exts]


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

def detect_sel_type(filepath: str) -> str:
    """Detect sel type from magic bytes first, fallback to file extension."""
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
    for sel_type, extensions in SEL_EXTENSIONS.items():
        if ext in extensions:
            return sel_type
    raise ValueError(f"Unsupported sel format: {ext}")


def is_sel_file(filepath: str) -> bool:
    """Check if a file has a supported sel extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in ALL_SEL_EXTS


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
    sel_data: bytes,
    sel_path: str,
    original_filename: str,
    original_data: bytes,
    password: str,
) -> bytes:
    """Build a polyglot media file."""
    sel_type = detect_sel_type(sel_path)
    
    salt = get_random_bytes(SALT_SIZE)
    key = derive_key(password, salt)
    
    cipher = AES.new(key, AES.MODE_GCM, nonce=get_random_bytes(NONCE_SIZE))
    
    filename_bytes = original_filename.encode("utf-8")
    filename_length = struct.pack(">H", len(filename_bytes))
    data_to_encrypt = filename_length + filename_bytes + original_data
    
    ciphertext, tag = cipher.encrypt_and_digest(data_to_encrypt)
    
    signature = hashlib.sha256(key + b"PARASYTE_SIG").digest()[:8]
    
    payload = signature + cipher.nonce + tag + ciphertext + salt

    if sel_type == "jpeg":
        jpeg_end = find_jpeg_end(sel_data)
        return sel_data[:jpeg_end] + payload
    elif sel_type == "png":
        png_end = find_png_end(sel_data)
        return sel_data[:png_end] + payload
    else:
        return sel_data + payload


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

    nonce = hidden[offset : offset + NONCE_SIZE]
    offset += NONCE_SIZE

    tag = hidden[offset : offset + TAG_SIZE]
    offset += TAG_SIZE

    ciphertext = hidden[offset : -SALT_SIZE]

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    decrypted_blob = cipher.decrypt_and_verify(ciphertext, tag)
    
    filename_length = struct.unpack(">H", decrypted_blob[:2])[0]
    original_filename = decrypted_blob[2 : 2 + filename_length].decode("utf-8")
    decrypted_data = decrypted_blob[2 + filename_length :]

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

def collect_sel_files(sel_path: str) -> list[str]:
    """Collect all sel files from a directory (recursive)."""
    if os.path.isfile(sel_path):
        if is_sel_file(sel_path):
            return [os.path.abspath(sel_path)]
        else:
            raise ValueError(f"File '{sel_path}' is not a supported sel format. Supported: {', '.join(ALL_SEL_EXTS)}")

    sel_files = []
    for root, _, files in os.walk(sel_path):
        for f in files:
            filepath = os.path.join(root, f)
            if is_sel_file(filepath):
                sel_files.append(os.path.abspath(filepath))

    if not sel_files:
        raise FileNotFoundError(f"No sel files found in '{sel_path}'. Supported: {', '.join(ALL_SEL_EXTS)}")

    return sorted(sel_files)


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
            if is_sel_file(filepath):
                files.append(os.path.abspath(filepath))

    if not files:
        raise FileNotFoundError(f"No media files found in '{input_path}'")

    return sorted(files)


def assign_sel_files(data_files: list[str], sel_files: list[str]) -> list[str]:
    """Assign a random sel to each data file."""
    n_data = len(data_files)
    n_sel_files = len(sel_files)

    if n_data <= n_sel_files:
        assigned = random.sample(sel_files, n_data)
    else:
        assigned = list(sel_files)
        remaining = n_data - n_sel_files
        assigned.extend(random.choices(sel_files, k=remaining))
        random.shuffle(assigned)

    return assigned
