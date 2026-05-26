"""Three escalating patch tests to isolate the corruption cause.

  Test A:  decompress + recompress ALL entries (zero modifications).
           If this breaks the game, recompression is broken.
  Test B:  same as A but for entry 48 only, write to a copy
  Test C:  modify ONE string in entry 48 with FULLWIDTH english padded
           to same byte length.  if this works -> ASCII was the problem.
"""
import os, sys, shutil, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, write_archive, decode_entry, lzss_pack
from ail_translate import extract_sjis_strings

JP_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
EN_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL_ENG_ver"

count, sizes, blobs = read_archive(os.path.join(JP_DIR, 'sall.snl'))

def to_fullwidth_sjis(text: str) -> bytes:
    """Convert ASCII to full-width Latin SJIS bytes (2 bytes per char)."""
    out = []
    for ch in text:
        c = ord(ch)
        if c == 0x20:
            out.append('　')  # fullwidth space
        elif 0x21 <= c <= 0x7E:
            out.append(chr(c - 0x20 + 0xFF00))  # FULLWIDTH range
        else:
            out.append('?')  # placeholder
    return ''.join(out).encode('shift_jis')

def pad_fullwidth_to_slot(text: str, slot_bytes: int) -> bytes:
    """Encode ASCII text as fullwidth SJIS, pad with fullwidth space to fit."""
    # First strip + collapse whitespace
    text = " ".join(text.split())
    # Greedy fit: encode and chop until fits
    raw = to_fullwidth_sjis(text)
    while len(raw) > slot_bytes:
        text = text[:-1].rstrip()
        raw = to_fullwidth_sjis(text)
    pad_bytes = slot_bytes - len(raw)
    if pad_bytes < 0:
        raw = raw[:slot_bytes]
    elif pad_bytes > 0:
        # pad with fullwidth space (81 40), which is 2 bytes
        n_fw = pad_bytes // 2
        n_half = pad_bytes - n_fw * 2
        raw = raw + b'\x81\x40' * n_fw + b' ' * n_half
    assert len(raw) == slot_bytes
    return raw

# ----- Choose the test mode -----
MODE = os.environ.get('TEST_MODE', 'A')  # A, B, or C
print(f"=== Running TEST {MODE} ===")

if MODE == 'A':
    # Pure decompress + recompress, no modifications
    new_blobs = []
    new_sizes = []
    for idx, blob in enumerate(blobs):
        if not blob:
            new_blobs.append(b'')
            new_sizes.append(0)
            continue
        payload, info = decode_entry(blob)
        if info.get('packed'):
            body = lzss_pack(payload)
            entry = struct.pack('<HI', 1, len(payload)) + body
        else:
            entry = blob
        new_blobs.append(entry)
        new_sizes.append(len(entry))
    out_path = os.path.join(EN_DIR, 'sall.snl')
    write_archive(out_path, new_sizes, new_blobs)
    print(f"  wrote {out_path}: pure recompress, no string mods")
    print(f"  size: {sum(new_sizes)+4+len(new_sizes)*4:,d} bytes (orig 524,561)")

elif MODE == 'B':
    # Only patch entry 48 (recompress all, modify nothing)
    payload, info = decode_entry(blobs[48])
    print(f"  entry 48 payload {len(payload)} bytes")
    # write back unchanged
    new_blobs = list(blobs)
    body = lzss_pack(payload)
    new_blobs[48] = struct.pack('<HI', 1, len(payload)) + body
    new_sizes = [len(b) for b in new_blobs]
    out_path = os.path.join(EN_DIR, 'sall.snl')
    write_archive(out_path, new_sizes, new_blobs)
    print(f"  wrote {out_path}: only entry 48 recompressed (no string mods)")

elif MODE == 'C':
    # Modify ONE string in entry 48 with fullwidth English
    payload, info = decode_entry(blobs[48])
    strs = extract_sjis_strings(payload, min_bytes=4)
    target = strs[0]  # first string
    off, ln, jp = target
    en = "Watch Opening"
    fw = pad_fullwidth_to_slot(en, ln)
    print(f"  patching @0x{off:04x} [{ln}B]: {jp!r} -> {fw!r}")
    new_payload = bytearray(payload)
    new_payload[off:off+ln] = fw
    new_blobs = list(blobs)
    body = lzss_pack(bytes(new_payload))
    new_blobs[48] = struct.pack('<HI', 1, len(new_payload)) + body
    new_sizes = [len(b) for b in new_blobs]
    out_path = os.path.join(EN_DIR, 'sall.snl')
    write_archive(out_path, new_sizes, new_blobs)
    print(f"  wrote {out_path}: entry 48 with ONE fullwidth-EN string")

print("\nNow copy this sall.snl to the actual game install dir and test:")
print(f"  copy /Y \"{out_path}\" \"D:\\game_install\\501game\\Kouhou\\kouhouDL_game\\kouhouDL\\sall.snl\"")
print(f"  then launch the game from there")
