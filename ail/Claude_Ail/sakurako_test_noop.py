"""Test: 'translate' sakurakoDL but replace each string with ITSELF (no-op).

This isolates whether voice breaks due to byte CHANGES or due to going
through the extract->replace->recompress pipeline. If no-op replacement
also breaks voice, then something in our pipeline subtly corrupts data
beyond the strings themselves.
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, write_archive, decode_entry, lzss_pack_all_literal
from ail_translate import extract_sjis_strings, find_strings_region, classify_strings_in_region

SAK_SRC = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"
OUT     = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL_ENG_ver\sall.snl.sakurako_test_noop"

count, sizes, blobs = read_archive(SAK_SRC)
total_strings = 0

new_blobs = []
new_sizes = []
for idx, blob in enumerate(blobs):
    if not blob:
        new_blobs.append(b''); new_sizes.append(0); continue
    payload, info = decode_entry(blob)
    if info.get('packed'):
        gross = extract_sjis_strings(payload)
        region = find_strings_region(gross)
        classified = classify_strings_in_region(payload, region)
        # No-op: write the SAME bytes back to each slot
        mutable = bytearray(payload)
        for off, ln, text, role in classified:
            if role not in ('ruby', 'voice_tag'):
                # write back the EXACT original bytes (no change)
                orig = payload[off:off+ln]
                mutable[off:off+ln] = orig
                total_strings += 1
        body = lzss_pack_all_literal(bytes(mutable))
        entry = struct.pack('<HI', 1, len(mutable)) + body
    else:
        entry = blob
    new_blobs.append(entry); new_sizes.append(len(entry))

write_archive(OUT, new_sizes, new_blobs)
print(f"Wrote {OUT}")
print(f"  total strings 'replaced' with themselves: {total_strings}")
print(f"  output size: {os.path.getsize(OUT):,d}")

# Verify byte-identity of payloads
import hashlib
count2, sizes2, blobs2 = read_archive(OUT)
n_packed_identical = 0
n_packed_total = 0
for idx in range(count):
    if not blobs[idx]: continue
    p1, info1 = decode_entry(blobs[idx])
    p2, info2 = decode_entry(blobs2[idx])
    if info1.get('packed'):
        n_packed_total += 1
        if p1 == p2:
            n_packed_identical += 1
print(f"  decoded payload identity: {n_packed_identical}/{n_packed_total}")

print(f"\nCopy and test:")
print(f'  copy /Y "{OUT}" "D:\\game_install\\501game\\Baiin Reijou Suouin Sakurako no Zaiwai\\SAKURAKODL\\sall.snl"')
