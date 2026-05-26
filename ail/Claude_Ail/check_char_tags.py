"""Count character name tags (full-width 【XXX】) in sakurakoDL strings."""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings, find_strings_region

# 【 = 0x81 0x79, 】 = 0x81 0x7A
OPEN_BRACKET  = b'\x81\x79'  # 【
CLOSE_BRACKET = b'\x81\x7A'  # 】

for label, path in [
    ('sakurakoDL', r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"),
    ('kouhouDL',   r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl"),
]:
    print(f"\n========== {label} ==========")
    count, sizes, blobs = read_archive(path)
    total_char_tags = 0
    char_names = set()
    for idx, blob in enumerate(blobs):
        if not blob: continue
        payload, info = decode_entry(blob)
        if not info.get('packed'): continue
        strs = extract_sjis_strings(payload)
        region = find_strings_region(strs)
        for off, ln, text in region:
            raw = payload[off:off+ln]
            if raw.startswith(OPEN_BRACKET) and raw.endswith(CLOSE_BRACKET):
                total_char_tags += 1
                # extract the name
                inner = raw[2:-2]
                try:
                    name = inner.decode('shift_jis')
                    char_names.add(name)
                except UnicodeDecodeError:
                    pass
    print(f"  total 【...】 character name tags: {total_char_tags}")
    print(f"  unique characters: {len(char_names)}")
    if char_names:
        print(f"  examples: {sorted(char_names)[:15]}")
