"""Hunt for offset references to strings in the bytecode region."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from ail_lzss import read_archive, decode_entry

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
count, sizes, blobs = read_archive(os.path.join(base, 'sall.snl'))

def find_sjis_strings(payload, min_chars=2):
    results = []
    i, n = 0, len(payload)
    while i < n:
        b = payload[i]
        if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) and i + 1 < n:
            b2 = payload[i+1]
            if 0x40 <= b2 <= 0xFC and b2 != 0x7F:
                start = i
                while i + 1 < n:
                    b = payload[i]
                    if not (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC): break
                    b2 = payload[i+1]
                    if not (0x40 <= b2 <= 0xFC and b2 != 0x7F): break
                    i += 2
                if i - start >= min_chars * 2:
                    try:
                        s = payload[start:i].decode('shift_jis')
                        results.append((start, i - start, s))
                    except UnicodeDecodeError:
                        pass
                continue
        i += 1
    return results

def find_string_region(payload):
    """Find offset where contiguous string region begins."""
    strs = find_sjis_strings(payload, min_chars=2)
    if not strs:
        return None, strs
    # First string offset
    return strs[0][0], strs

# Test multiple entries for string-reference patterns
for idx in [0, 1, 50, 100, 5]:
    if not blobs[idx]:
        continue
    payload, info = decode_entry(blobs[idx])
    region_start, strs = find_string_region(payload)
    if region_start is None:
        print(f"--- entry {idx}: no strings")
        continue
    str_offsets = set(s[0] for s in strs)
    bytecode = payload[:region_start]
    print(f"--- entry {idx}: {len(payload)} bytes, strings start at 0x{region_start:04x}, {len(strs)} strings, bytecode={len(bytecode)}B")

    # Search for u16 references to string offsets in bytecode
    u16_refs = {}  # off_in_bytecode -> string_offset
    for off in range(0, len(bytecode) - 1):
        v = struct.unpack_from('<H', bytecode, off)[0]
        if v in str_offsets:
            u16_refs[off] = v
    print(f"    u16 refs to string starts in bytecode: {len(u16_refs)}/{len(strs)} strings referenced")

    # Sample a few
    if u16_refs:
        sample = list(u16_refs.items())[:5]
        for byte_off, str_off in sample:
            # context
            ctx = bytecode[max(0,byte_off-4):byte_off+8].hex()
            # decode string
            decoded = next((s for o, bl, s in strs if o == str_off), '?')
            print(f"      bytecode@0x{byte_off:04x} -> str@0x{str_off:04x}  ctx={ctx}  '{decoded[:30]}'")

    # also check for stride patterns (e.g. table of refs every 4 bytes)
    if u16_refs:
        offsets_sorted = sorted(u16_refs.keys())
        if len(offsets_sorted) > 1:
            diffs = [offsets_sorted[i+1] - offsets_sorted[i] for i in range(len(offsets_sorted)-1)]
            from collections import Counter
            print(f"    distance between consecutive refs: {Counter(diffs).most_common(5)}")
    print()
