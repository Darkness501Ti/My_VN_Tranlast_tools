"""Look for voice trigger markers near dialogue strings in sakurakoDL.

Hypothesis: voice playback is tied to specific bytes adjacent to or inside
dialogue strings. Our translation might be wiping them.
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings

snl_sak = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"
snl_kou = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl"

for label, path in [('sakurakoDL', snl_sak), ('kouhouDL', snl_kou)]:
    print(f"\n========== {label} ==========")
    count, sizes, blobs = read_archive(path)
    # Pick an entry with dialogue (sakurakoDL entry 51, kouhouDL entry 50)
    idx = 51 if 'sak' in label else 50
    payload, info = decode_entry(blobs[idx])
    strs = extract_sjis_strings(payload, min_bytes=8)
    # Look at the dialogue cluster — the last ~10 strings
    print(f"  entry {idx}: {len(payload)} bytes")
    print(f"\n  Bytes BEFORE each dialogue string (4 bytes preceding):")
    for off, ln, s in strs[:20]:
        pre = payload[max(0, off-4):off]
        # also look at 4 bytes after
        post = payload[off+ln:off+ln+4]
        print(f"    @0x{off:04x} pre={pre.hex():<10} post={post.hex():<10} text={s[:30]!r}")

    print(f"\n  Looking for patterns BEFORE dialogue strings...")
    # Common pattern? E.g. all preceded by `00 XX 00 00`?
    from collections import Counter
    pre_2 = Counter()
    pre_4 = Counter()
    for off, ln, s in strs:
        if off >= 4:
            pre_2[payload[off-2:off].hex()] += 1
            pre_4[payload[off-4:off].hex()] += 1
    print(f"  Most common 2-byte prefix: {pre_2.most_common(5)}")
    print(f"  Most common 4-byte prefix: {pre_4.most_common(5)}")
