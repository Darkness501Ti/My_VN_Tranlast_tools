"""Dry-run test: exercise the full pipeline with a MOCK translator.

This verifies decompress -> extract -> replace -> recompress -> archive write
without calling Sugoi. Reads sall.snl, translates strings to a deterministic
mock ("EN:<orig>"), writes patched sall.snl_test next to it, then re-reads
the patched archive and confirms it parses cleanly and contains the mock
strings.
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, write_archive, decode_entry, lzss_pack
from ail_translate import extract_sjis_strings, english_to_sjis_slot

GAME_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"

def mock_translate(s: str) -> str:
    """Deterministic mock: prefix with ascii letters of length 1 per JP char."""
    # produce predictable ASCII to verify replacement worked
    return f"[EN] line {len(s)}c {''.join('x' for _ in s)}"

def main():
    src = os.path.join(GAME_DIR, 'sall.snl')
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sall.snl.test')

    print(f"[+] Reading {src}")
    count, sizes, blobs = read_archive(src)

    total_strings = 0
    total_bytes_in_strings = 0
    entry_payloads = []  # (idx, packed?, payload-bytes)
    for idx, blob in enumerate(blobs):
        if not blob:
            entry_payloads.append((idx, False, b''))
            continue
        payload, info = decode_entry(blob)
        if info.get('packed'):
            strs = extract_sjis_strings(payload)
            mutable = bytearray(payload)
            for off, ln, s in strs:
                en = mock_translate(s)
                new_bytes = english_to_sjis_slot(en, ln)
                mutable[off:off+ln] = new_bytes
                total_strings += 1
                total_bytes_in_strings += ln
            entry_payloads.append((idx, True, bytes(mutable)))
        else:
            entry_payloads.append((idx, False, blob))

    print(f"[+] Mock-translated {total_strings} strings ({total_bytes_in_strings:,} bytes)")

    # Recompress and write
    new_blobs = []
    new_sizes = []
    for idx, packed, p in entry_payloads:
        if not blobs[idx]:
            new_blobs.append(b'')
            new_sizes.append(0)
        elif packed:
            packed_body = lzss_pack(p)
            unpacked = len(p)
            prefix = struct.pack('<HI', 1, unpacked)
            entry = prefix + packed_body
            new_blobs.append(entry)
            new_sizes.append(len(entry))
        else:
            new_blobs.append(p)
            new_sizes.append(len(p))

    write_archive(dst, new_sizes, new_blobs)
    print(f"[+] Wrote {dst}")
    print(f"    original size : {os.path.getsize(src):>10,d}")
    print(f"    patched  size : {os.path.getsize(dst):>10,d}")

    # Re-read and verify
    print(f"\n[+] Re-reading patched archive and verifying...")
    count2, sizes2, blobs2 = read_archive(dst)
    assert count2 == count, f"count mismatch: {count2} vs {count}"
    print(f"    count match : {count2}")

    # Pick a known-translated entry and verify it decodes
    test_idx = 0  # menu entry, has strings
    payload2, info2 = decode_entry(blobs2[test_idx])
    print(f"    entry {test_idx} decoded: {len(payload2)} bytes (packed={info2.get('packed')})")

    # Original strings:
    orig_payload, _ = decode_entry(blobs[test_idx])
    orig_strs = extract_sjis_strings(orig_payload)
    print(f"\n    original entry {test_idx} strings:")
    for off, ln, s in orig_strs[:5]:
        print(f"      @0x{off:04x} [{ln}B] {s!r}")

    print(f"\n    patched entry {test_idx} at same offsets:")
    for off, ln, _ in orig_strs[:5]:
        new_bytes = payload2[off:off+ln]
        print(f"      @0x{off:04x} [{ln}B] {new_bytes!r}")

    # confirm all original-payload-length entries decode to expected unpacked size
    fail = 0
    for idx in range(count):
        if not blobs2[idx]:
            continue
        try:
            p, info = decode_entry(blobs2[idx])
            if info.get('packed'):
                # check expected unpacked matches our payload
                expected = len(entry_payloads[idx][2])
                if len(p) != expected:
                    print(f"    ✗ entry {idx}: decompressed to {len(p)}, expected {expected}")
                    fail += 1
        except Exception as e:
            print(f"    ✗ entry {idx}: decode failed: {e}")
            fail += 1
    if fail == 0:
        print(f"\n[+] All {count} entries verify clean.")
    else:
        print(f"\n[!] {fail} entries failed verification.")
        return 1

    # cleanup
    try:
        os.remove(dst)
        print(f"[+] Removed test archive {dst}")
    except OSError:
        pass
    return 0

if __name__ == '__main__':
    sys.exit(main())
