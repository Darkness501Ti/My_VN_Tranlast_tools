"""Verify LZSS decompress->recompress->decompress yields identical bytes."""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from ail_lzss import read_archive, decode_entry, lzss_unpack, lzss_pack

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
count, sizes, blobs = read_archive(os.path.join(base, 'sall.snl'))

print(f"Testing LZSS round-trip on all {count} entries of sall.snl...")
fail = 0
ok = 0
size_ratio_sum = 0
n_packed = 0
for idx, blob in enumerate(blobs):
    if not blob:
        continue
    payload, info = decode_entry(blob)
    if not info.get('packed'):
        continue
    # try recompress
    recompressed = lzss_pack(payload)
    # decompress recompressed
    redecoded = lzss_unpack(recompressed, len(payload))
    if redecoded != payload:
        fail += 1
        print(f"  ✗ entry {idx}: ROUND-TRIP FAILED ({len(payload)} bytes)")
        # diff
        for i in range(min(len(payload), len(redecoded))):
            if payload[i] != redecoded[i]:
                print(f"      first diff at byte {i}: orig=0x{payload[i]:02x} got=0x{redecoded[i]:02x}")
                break
        if fail >= 3:
            break
    else:
        ok += 1
        n_packed += 1
        orig_packed_size = len(blob) - 6
        size_ratio_sum += len(recompressed) / orig_packed_size

print(f"\nResults: {ok} ok, {fail} fail")
if n_packed:
    print(f"Avg compression ratio (new vs orig): {size_ratio_sum/n_packed:.3f}")
