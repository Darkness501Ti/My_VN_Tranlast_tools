"""Find JP strings in sall.snl that we MISSED translating."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings, find_strings_region, classify_strings_in_region

# Look at the JP source sall.snl (we don't have a JP copy of sakurakoDL, just install dir)
SRC = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"
if not os.path.isfile(SRC):
    candidates = [
        r"D:\game_install\501Translate\waiting to Tranlaste\JP\SAKURAKODL\sall.snl",
        r"D:\game_install\501Translate\waiting to Tranlaste\JP\sakurakoDL\sall.snl",
        r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\SAKURAKODL\sall.snl.JP_backup",
    ]
    for c in candidates:
        if os.path.isfile(c):
            SRC = c
            break
    else:
        print("[!] No JP backup of sakurakoDL sall.snl found.")
        print("    Tried:")
        for c in candidates:
            print(f"      {c}")
        sys.exit(1)

print(f"[+] Using JP source: {SRC}")

# Target text: "次の授業も" should be in some entry
needle = "次の授業も".encode('shift_jis')
needle2 = "クラスメイト".encode('shift_jis')
needle3 = "一日の授業".encode('shift_jis')

count, sizes, blobs = read_archive(SRC)
print(f"sall.snl: {count} entries")

# scan each entry for the needle
hits = []
for idx, blob in enumerate(blobs):
    if not blob: continue
    try:
        payload, info = decode_entry(blob)
    except:
        continue
    for nm, n in [("次の授業も", needle), ("クラスメイト", needle2), ("一日の授業", needle3)]:
        pos = payload.find(n)
        if pos >= 0:
            hits.append((idx, nm, pos, len(payload)))

print(f"\nFound {len(hits)} hits:")
for idx, nm, pos, plen in hits:
    print(f"  entry {idx} ({plen}B): {nm!r} at 0x{pos:04x}")

if hits:
    # Focus on the entry containing 次の授業も
    target_idx = None
    for idx, nm, pos, plen in hits:
        if nm == "次の授業も":
            target_idx = idx
            break
    if target_idx is None:
        target_idx = hits[0][0]
    payload, info = decode_entry(blobs[target_idx])
    print(f"\n=== Analyzing entry {target_idx} ({len(payload)}B) ===")

    gross = extract_sjis_strings(payload)
    region = find_strings_region(gross)
    classified = classify_strings_in_region(payload, region)

    print(f"  total SJIS detected: {len(gross)}")
    print(f"  in region (after heuristic): {len(region)}")
    print(f"  classified base/ruby: {sum(1 for *_, r in classified if r=='base')}/{sum(1 for *_, r in classified if r=='ruby')}")
    print(f"  EXCLUDED by gap heuristic: {len(gross) - len(region)}")

    # What's the first string in region?
    if region:
        print(f"\n  Region range: 0x{region[0][0]:04x} .. 0x{region[-1][0]:04x}")
    # What's the first string with the JP target?
    region_offsets = set(s[0] for s in region)
    pos_target = payload.find(needle)
    print(f"\n  '次の授業も' at offset 0x{pos_target:04x}")
    print(f"  In region? {pos_target in region_offsets}")

    # show EXCLUDED strings
    excluded = [s for s in gross if s[0] not in region_offsets]
    print(f"\n  Sample of {min(20, len(excluded))} EXCLUDED 'strings' (would not be translated):")
    for off, ln, s in excluded[:20]:
        # is it JP-looking or noise?
        is_real = any(c in s for c in 'のはのにをがでとも')
        marker = '<- LOOKS REAL' if is_real else '(probably bytecode noise)'
        print(f"    @0x{off:04x} [{ln}B] {s!r}  {marker}")

    # show region's first few
    print(f"\n  Region first 5 strings:")
    for off, ln, s in region[:5]:
        print(f"    @0x{off:04x} [{ln}B] {s!r}")
