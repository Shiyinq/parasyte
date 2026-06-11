"""Quick verification test for Parasyte encrypt/decrypt roundtrip."""

import hashlib
import os
import sys

from core import (
    assign_carriers,
    build_polyglot,
    collect_carriers,
    collect_dna_files,
    detect_carrier_type,
    cure_and_extract,
)

TEST_PASSWORD = "test_password_123"
DATA_DIR = "dna"
BUCKET_DIR = "carriers"


def test_single_roundtrip(dna_path: str, carrier_path: str):
    """Test encrypt/decrypt roundtrip for a single DNA + carrier pair."""
    carrier_name = os.path.basename(carrier_path)
    dna_name = os.path.basename(dna_path)
    carrier_type = detect_carrier_type(carrier_path)

    # Read original DNA
    with open(dna_path, "rb") as f:
        original_dna = f.read()
    original_hash = hashlib.sha256(original_dna).hexdigest()

    # Read carrier
    with open(carrier_path, "rb") as f:
        carrier_data = f.read()

    # Build polyglot
    polyglot = build_polyglot(carrier_data, carrier_path, dna_name, original_dna, TEST_PASSWORD)

    # Validate file header
    if carrier_type == "jpeg":
        assert polyglot[:2] == b"\xff\xd8", "Not a valid JPEG"
    elif carrier_type == "png":
        assert polyglot[:8] == b"\x89PNG\r\n\x1a\n", "Not a valid PNG"
    elif carrier_type == "mp4":
        pass  # MP4 header varies
    elif carrier_type == "mkv":
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

    print(f"  ✅ {dna_name} + {carrier_name} ({carrier_type}) — "
          f"{len(original_dna):,} → {len(polyglot):,} bytes")

    return polyglot


def test_carrier_assignment():
    """Test the random carrier assignment logic."""
    print("\n📋 Testing carrier assignment logic...")

    carriers = ["A.jpg", "B.mp4", "C.mkv", "D.jpg", "E.jpeg"]

    # Case 1: data <= carriers (unique assignment)
    data_3 = ["file1", "file2", "file3"]
    assigned = assign_carriers(data_3, carriers)
    assert len(assigned) == 3, f"Expected 3, got {len(assigned)}"
    assert len(set(assigned)) == 3, "Should have unique carriers when data <= carriers"
    print(f"  ✅ 3 data, 5 carriers → {len(set(assigned))} unique assignments")

    # Case 2: data == carriers
    data_5 = ["f1", "f2", "f3", "f4", "f5"]
    assigned = assign_carriers(data_5, carriers)
    assert len(assigned) == 5
    assert len(set(assigned)) == 5, "Should use all carriers when data == carriers"
    print(f"  ✅ 5 data, 5 carriers → {len(set(assigned))} unique assignments")

    # Case 3: data > carriers (reuse)
    data_8 = [f"f{i}" for i in range(8)]
    assigned = assign_carriers(data_8, carriers)
    assert len(assigned) == 8
    assert set(carriers).issubset(set(assigned)), "All carriers should be used at least once"
    print(f"  ✅ 8 data, 5 carriers → {len(assigned)} assignments, "
          f"{len(set(assigned))} unique carriers (reuse expected)")

    # Case 4: Verify randomness
    results = set()
    for _ in range(20):
        assigned = assign_carriers(data_3, carriers)
        results.add(tuple(assigned))
    assert len(results) > 1, "Assignments should be random"
    print(f"  ✅ Randomness check: {len(results)} unique orderings in 20 runs")


def main():
    print("🧪 Running Parasyte verification tests...\n")

    # 1. Test carrier assignment logic
    test_carrier_assignment()

    # 2. Test roundtrip for each carrier with each DNA file
    print("\n📦 Testing infect/cure roundtrip...")

    dna_files = collect_dna_files(DATA_DIR)
    carriers = collect_carriers(BUCKET_DIR)

    print(f"   DNA files:  {len(dna_files)}")
    print(f"   Carriers:   {len(carriers)}")
    print()

    passed = 0
    failed = 0
    for dna_file in dna_files:
        for carrier in carriers:
            try:
                test_single_roundtrip(dna_file, carrier)
                passed += 1
            except Exception as e:
                print(f"  ❌ {os.path.basename(dna_file)} + "
                      f"{os.path.basename(carrier)} — {e}")
                failed += 1

    # 3. Save one example for manual inspection
    print("\n📁 Saving example infected file for manual inspection...")
    if dna_files and carriers:
        polyglot = test_single_roundtrip(dna_files[0], carriers[0])
        ext = os.path.splitext(carriers[0])[1]
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
