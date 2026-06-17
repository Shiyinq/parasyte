"""Quick verification test for Parasyte encrypt/decrypt roundtrip."""

import hashlib
import os
import sys

from core import (
    assign_sel_files,
    build_polyglot,
    build_raw_payload,
    collect_sel_files,
    collect_dna_files,
    detect_sel_type,
    cure_and_extract,
)

TEST_PASSWORD = "test_password_123"
DATA_DIR = "dna"
BUCKET_DIR = "sel"


def test_single_roundtrip(dna_path: str, sel_path: str):
    """Test encrypt/decrypt roundtrip for a single DNA + sel pair."""
    sel_name = os.path.basename(sel_path)
    dna_name = os.path.basename(dna_path)
    sel_type = detect_sel_type(sel_path)

    # Read original DNA
    with open(dna_path, "rb") as f:
        original_dna = f.read()
    original_hash = hashlib.sha256(original_dna).hexdigest()

    # Read sel
    with open(sel_path, "rb") as f:
        sel_data = f.read()

    # Build polyglot
    polyglot = build_polyglot(sel_data, sel_path, dna_name, original_dna, TEST_PASSWORD)

    # Validate file header
    if sel_type == "jpeg":
        assert polyglot[:2] == b"\xff\xd8", "Not a valid JPEG"
    elif sel_type == "png":
        assert polyglot[:8] == b"\x89PNG\r\n\x1a\n", "Not a valid PNG"
    elif sel_type == "mp4":
        pass  # MP4 header varies
    elif sel_type == "mkv":
        pass  # MKV header varies

    # Extract and Decrypt
    restored_filename, decrypted_dna = cure_and_extract(polyglot, TEST_PASSWORD)
    assert restored_filename == dna_name, f"Filename mismatch: {restored_filename}"

    decrypted_hash = hashlib.sha256(decrypted_dna).hexdigest()

    # Verify integrity
    assert original_hash == decrypted_hash, "HASH MISMATCH!"
    assert original_dna == decrypted_dna, "DNA MISMATCH!"

    # Test wrong password
    try:
        cure_and_extract(polyglot, "wrong_password")
        assert False, "Wrong password should have raised an error!"
    except ValueError:
        pass  # Expected

    print(f"  ✅ {dna_name} + {sel_name} ({sel_type}) — "
          f"{len(original_dna):,} → {len(polyglot):,} bytes")

    return polyglot


def test_raw_roundtrip(dna_path: str):
    """Test raw encrypt/decrypt roundtrip (no media disguise)."""
    dna_name = os.path.basename(dna_path)

    with open(dna_path, "rb") as f:
        original_dna = f.read()
    original_hash = hashlib.sha256(original_dna).hexdigest()

    # Build raw payload
    payload = build_raw_payload(dna_name, original_dna, TEST_PASSWORD)

    # Decrypt
    restored_filename, decrypted_dna = cure_and_extract(payload, TEST_PASSWORD)
    assert restored_filename == dna_name, f"Filename mismatch: {restored_filename}"

    decrypted_hash = hashlib.sha256(decrypted_dna).hexdigest()
    assert original_hash == decrypted_hash, "HASH MISMATCH!"
    assert original_dna == decrypted_dna, "DNA MISMATCH!"

    # Test wrong password
    try:
        cure_and_extract(payload, "wrong_password")
        assert False, "Wrong password should have raised an error!"
    except ValueError:
        pass

    print(f"  ✅ [RAW] {dna_name} — "
          f"{len(original_dna):,} → {len(payload):,} bytes")


def test_sel_assignment():
    """Test the random sel assignment logic."""
    print("\n📋 Testing sel assignment logic...")

    sel_files = ["A.jpg", "B.mp4", "C.mkv", "D.jpg", "E.jpeg"]

    # Case 1: data <= sel_files (unique assignment)
    data_3 = ["file1", "file2", "file3"]
    assigned = assign_sel_files(data_3, sel_files)
    assert len(assigned) == 3, f"Expected 3, got {len(assigned)}"
    assert len(set(assigned)) == 3, "Should have unique sel_files when data <= sel_files"
    print(f"  ✅ 3 data, 5 sel_files → {len(set(assigned))} unique assignments")

    # Case 2: data == sel_files
    data_5 = ["f1", "f2", "f3", "f4", "f5"]
    assigned = assign_sel_files(data_5, sel_files)
    assert len(assigned) == 5
    assert len(set(assigned)) == 5, "Should use all sel_files when data == sel_files"
    print(f"  ✅ 5 data, 5 sel_files → {len(set(assigned))} unique assignments")

    # Case 3: data > sel_files (reuse)
    data_8 = [f"f{i}" for i in range(8)]
    assigned = assign_sel_files(data_8, sel_files)
    assert len(assigned) == 8
    assert set(sel_files).issubset(set(assigned)), "All sel_files should be used at least once"
    print(f"  ✅ 8 data, 5 sel_files → {len(assigned)} assignments, "
          f"{len(set(assigned))} unique sel_files (reuse expected)")

    # Case 4: Verify randomness
    results = set()
    for _ in range(20):
        assigned = assign_sel_files(data_3, sel_files)
        results.add(tuple(assigned))
    assert len(results) > 1, "Assignments should be random"
    print(f"  ✅ Randomness check: {len(results)} unique orderings in 20 runs")


def main():
    print("🧪 Running Parasyte verification tests...\n")

    # 1. Test sel assignment logic
    test_sel_assignment()

    # 2. Test roundtrip for each sel with each DNA file
    print("\n📦 Testing infect/cure roundtrip...")

    dna_files = collect_dna_files(DATA_DIR)
    sel_files = collect_sel_files(BUCKET_DIR)

    print(f"   DNA files:  {len(dna_files)}")
    print(f"   Sels:   {len(sel_files)}")
    print()

    passed = 0
    failed = 0
    for dna_file in dna_files:
        for sel in sel_files:
            try:
                test_single_roundtrip(dna_file, sel)
                passed += 1
            except Exception as e:
                print(f"  ❌ {os.path.basename(dna_file)} + "
                      f"{os.path.basename(sel)} — {e}")
                failed += 1

    # 3. Test raw encrypt/decrypt roundtrip
    print("\n📦 Testing raw encrypt/decrypt roundtrip...")
    for dna_file in dna_files:
        try:
            test_raw_roundtrip(dna_file)
            passed += 1
        except Exception as e:
            print(f"  ❌ [RAW] {os.path.basename(dna_file)} — {e}")
            failed += 1

    # 4. Save one example for manual inspection
    print("\n📁 Saving example infected file for manual inspection...")
    if dna_files and sel_files:
        polyglot = test_single_roundtrip(dna_files[0], sel_files[0])
        ext = os.path.splitext(sel_files[0])[1]
        output_path = f"hive/test_output{ext}"
        os.makedirs("hive", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(polyglot)
        print(f"  💾 Saved to '{output_path}'")

    print(f"\n{'='*50}")
    print(f"🎉 Results: {passed} passed, {failed} failed")
    print(f"{'='*50}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
