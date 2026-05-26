"""Test: recompress sakurakoDL's sall.snl with all-literal LZSS, NO string mods.

If voice auto-plays after this: my STRING MODIFICATIONS break voice.
If voice still broken: my LZSS recompression breaks voice on this game
  (the engine reads the compressed stream itself for voice mapping, or
  has a hash check sensitive to compressed bytes).
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, write_archive, decode_entry, lzss_pack_all_literal

SAK_SRC = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"
OUT     = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL_ENG_ver\sall.snl.sakurako_test_A"

count, sizes, blobs = read_archive(SAK_SRC)
new_blobs = []
new_sizes = []
for idx, blob in enumerate(blobs):
    if not blob:
        new_blobs.append(b''); new_sizes.append(0); continue
    payload, info = decode_entry(blob)
    if info.get('packed'):
        body = lzss_pack_all_literal(payload)
        entry = struct.pack('<HI', 1, len(payload)) + body
    else:
        entry = blob
    new_blobs.append(entry); new_sizes.append(len(entry))

write_archive(OUT, new_sizes, new_blobs)
print(f"Wrote {OUT}")
print(f"  original   : {os.path.getsize(SAK_SRC):,d} bytes")
print(f"  recompress : {os.path.getsize(OUT):,d} bytes")
print()
print(f"Test this file by:")
print(f'  copy /Y "{OUT}" "D:\\game_install\\501game\\Baiin Reijou Suouin Sakurako no Zaiwai\\SAKURAKODL\\sall.snl"')
print(f"  launch sakurakoDL.exe")
print(f"  start new game, see if voice auto-plays")
