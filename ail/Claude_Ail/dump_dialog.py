"""Hex dump bytes around dialogue clusters to understand opcode structure."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
data = open(os.path.join(base, 'sall.snl'), 'rb').read()
count = struct.unpack_from('<I', data, 0)[0]
sizes = list(struct.unpack_from(f'<{count}I', data, 4))
hdr_end = 4 + count*4
blobs = []
off = hdr_end
for s in sizes:
    blobs.append(data[off:off+s] if s else b'')
    off += s

def hexdump_annotated(blob, start, length):
    """Print hex with sjis interpretation on a per-byte basis."""
    end = min(start+length, len(blob))
    out = []
    i = start
    while i < end:
        # try to render this as SJIS char if valid pair
        b = blob[i]
        if i+1 < end and (0x81<=b<=0x9F or 0xE0<=b<=0xFC) and (0x40<=blob[i+1]<=0xFC and blob[i+1]!=0x7F):
            try:
                ch = bytes([b, blob[i+1]]).decode('shift_jis')
                out.append(f"[{ch}]")
                i += 2
                continue
            except:
                pass
        if b == 0x00:
            out.append("·")
        elif 0x20 <= b <= 0x7E:
            out.append(chr(b))
        else:
            out.append(f"<{b:02x}>")
        i += 1
    return ' '.join(out)

# Dump entry 50 around byte 0x780 to 0x900
blob = blobs[50]
print(f"=== Entry 50, bytes 0x780..0x900 ===")
print(hexdump_annotated(blob, 0x780, 0x180))
print()

# Entry 100 - shorter, look at full structure
blob = blobs[100]
print(f"=== Entry 100, bytes 0x2e0..0x540 ===")
print(hexdump_annotated(blob, 0x2e0, 0x260))
print()

# Entry 2 header pattern
blob = blobs[2]
print(f"=== Entry 2, FIRST 200 bytes ===")
print(hexdump_annotated(blob, 0, 200))
print()

# Look at very end of entries (probable end marker)
for idx in [0, 1, 2, 50, 100]:
    blob = blobs[idx]
    if not blob: continue
    print(f"=== Entry {idx}, LAST 32 bytes (size={len(blob)}) ===")
    print(hexdump_annotated(blob, max(0, len(blob)-32), 32))
print()
