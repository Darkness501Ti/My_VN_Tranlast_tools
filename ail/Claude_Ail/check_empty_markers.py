"""Check if original sall.snl uses 0xFFFFFFFF for empty slots and if my code preserves them."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl"
EN = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL_ENG_ver\sall.snl"

for label, path in [('ORIGINAL', JP), ('MINE', EN)]:
    if not os.path.isfile(path):
        print(f"{label}: missing")
        continue
    with open(path, 'rb') as f:
        data = f.read()
    count = struct.unpack_from('<I', data, 0)[0]
    sizes = list(struct.unpack_from(f'<{count}I', data, 4))
    n_zero = sum(1 for s in sizes if s == 0)
    n_ff   = sum(1 for s in sizes if s == 0xFFFFFFFF)
    n_data = sum(1 for s in sizes if 0 < s < 0xFFFFFFFF)
    print(f"{label}: total={count} zero={n_zero} 0xFFFFFFFF={n_ff} data={n_data} file={len(data):,d}")
    # which indices are 0xFFFFFFFF?
    ff_idx = [i for i, s in enumerate(sizes) if s == 0xFFFFFFFF]
    if ff_idx:
        print(f"  0xFFFFFFFF indices: {ff_idx}")
    # also: header u32 count
    print(f"  header count u32: {data[:4].hex()}")
    # first few sizes for visual comparison
    print(f"  first 20 sizes : {sizes[:20]}")
    print()
