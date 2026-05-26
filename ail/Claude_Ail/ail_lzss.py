"""Ail engine LZSS decoder + archive reader, Python port of GARbro's ArcAil.cs.

Format reference (https://github.com/morkt/GARbro/blob/master/ArcFormats/Ail/ArcAil.cs)

Archive layout:
  u32 count
  u32 size[count]            # 0 or 0xFFFFFFFF == empty slot
  data[]                      # entries concatenated in order

Per-entry 6-byte prefix:
  u32 signature              # bytes 0..3
  u16 unpacked_size_lo/hi    # if (signature & 0xFFFF) == 1, then bytes 2..5 = u32 unpacked_size

If (signature & 0xFFFF) == 1:  entry payload is LZSS-compressed (extra=6, IsPacked)
Elif signature == 0 or ASCII("OggS") at offset+4: extra=4 (no prefix)
Else: extra=6, raw

LZSS (custom Ail variant):
  frame: 0x1000 bytes pre-init to 0x20 (' '), frame_pos = 0xFEE
  Read control byte; "0" bit = literal; "1" bit = back-ref
  Back-ref: read offset_lo, then b2; offset = offset_lo | ((b2 & 0xF0)<<4); count = (b2 & 0x0F) + 3
"""
from __future__ import annotations
import struct
from typing import List, Tuple, Optional


def lzss_unpack(input_bytes: bytes, output_size: int) -> bytes:
    """Decompress Ail-LZSS payload. Returns exactly `output_size` bytes."""
    frame = bytearray(0x1000)
    for i in range(0xFEE):
        frame[i] = 0x20
    frame_pos = 0xFEE
    output = bytearray(output_size)
    dst = 0
    src = 0
    ctl = 0
    n_in = len(input_bytes)
    while dst < output_size:
        ctl >>= 1
        if 0 == (ctl & 0x100):
            if src >= n_in:
                break
            ctl = input_bytes[src]; src += 1
            ctl |= 0xFF00
        if 0 == (ctl & 1):
            if src >= n_in:
                break
            v = input_bytes[src]; src += 1
            output[dst] = v; dst += 1
            frame[frame_pos] = v
            frame_pos = (frame_pos + 1) & 0xFFF
        else:
            if src + 1 >= n_in:
                break
            offset = input_bytes[src]; src += 1
            b2 = input_bytes[src]; src += 1
            offset |= (b2 & 0xF0) << 4
            count = (b2 & 0x0F) + 3
            for _ in range(count):
                if dst >= output_size:
                    break
                v = frame[offset]
                offset = (offset + 1) & 0xFFF
                frame[frame_pos] = v
                frame_pos = (frame_pos + 1) & 0xFFF
                output[dst] = v; dst += 1
    return bytes(output)


def lzss_pack(input_bytes: bytes) -> bytes:
    """Compress data using Ail-LZSS format (custom encoder).

    Uses greedy longest-match search through pre-initialized 4KB frame.
    Produces output that round-trips through lzss_unpack -> original bytes.
    """
    n = len(input_bytes)
    if n == 0:
        return b''

    frame = bytearray(0x1000)
    for i in range(0xFEE):
        frame[i] = 0x20
    frame_pos = 0xFEE

    src = 0
    out = bytearray()
    # We build 8 ops at a time; control byte holds 8 bits, LSB = first op
    while src < n:
        ops = bytearray()
        ctl = 0
        bits = 0
        while bits < 8 and src < n:
            # find longest match for input[src..]
            best_len = 0
            best_off = 0
            max_len = min(18, n - src)
            if max_len >= 3:
                # Search frame for longest prefix match.
                # Constraint: the Ail LZSS decoder reads from frame[offset]
                # and writes to frame[frame_pos] concurrently. If the read
                # pointer reaches the write pointer mid-match, reads return
                # newly-written bytes. To keep this encoder safe we cap each
                # candidate match to d = (frame_pos - off) mod 4096, the
                # distance before write catches read.
                target = input_bytes[src:src + max_len]
                t0 = target[0]
                for off in range(0x1000):
                    if frame[off] != t0:
                        continue
                    d = (frame_pos - off) & 0xFFF
                    if d == 0:
                        continue
                    max_safe = min(max_len, d)
                    L = 1
                    while L < max_safe and frame[(off + L) & 0xFFF] == target[L]:
                        L += 1
                    if L > best_len:
                        best_len = L
                        best_off = off
            if best_len >= 3:
                # emit back-ref op: ctl bit = 1
                ctl |= (1 << bits)
                b1 = best_off & 0xFF
                b2 = ((best_off >> 4) & 0xF0) | ((best_len - 3) & 0x0F)
                ops.append(b1)
                ops.append(b2)
                for k in range(best_len):
                    frame[frame_pos] = input_bytes[src + k]
                    frame_pos = (frame_pos + 1) & 0xFFF
                src += best_len
            else:
                # literal: ctl bit = 0
                v = input_bytes[src]
                ops.append(v)
                frame[frame_pos] = v
                frame_pos = (frame_pos + 1) & 0xFFF
                src += 1
            bits += 1
        out.append(ctl)
        out.extend(ops)
    return bytes(out)


def read_archive(path: str) -> Tuple[int, List[int], List[bytes]]:
    """Read .dat/.snl archive. Returns (count, raw_sizes, raw_entry_bytes_including_prefix).

    Each entry blob is returned with its 6-byte (or 4-byte) prefix intact.
    Empty slots (size=0 or 0xFFFFFFFF) return b'' with their original size marker.
    """
    with open(path, 'rb') as f:
        data = f.read()
    count = struct.unpack_from('<I', data, 0)[0]
    sizes = list(struct.unpack_from(f'<{count}I', data, 4))
    off = 4 + count * 4
    blobs = []
    for s in sizes:
        if s == 0 or s == 0xFFFFFFFF:
            blobs.append(b'')
        else:
            blobs.append(data[off:off + s])
            off += s
    return count, sizes, blobs


def write_archive(path: str, sizes: List[int], blobs: List[bytes]) -> None:
    """Write archive with given sizes and concatenated blobs."""
    assert len(sizes) == len(blobs)
    with open(path, 'wb') as f:
        f.write(struct.pack('<I', len(sizes)))
        for s in sizes:
            f.write(struct.pack('<I', s))
        for b in blobs:
            f.write(b)


def decode_entry(blob: bytes) -> Tuple[bytes, dict]:
    """Decode one archive entry: skip prefix, decompress if needed.

    Returns (payload, info) where info has {'packed', 'extra', 'unpacked_size', 'signature'}.
    """
    if not blob:
        return b'', {'packed': False, 'extra': 0}
    if len(blob) < 6:
        return blob, {'packed': False, 'extra': 0}
    sig_u32 = struct.unpack_from('<I', blob, 0)[0]
    info = {'signature': sig_u32}
    if (sig_u32 & 0xFFFF) == 1:
        unpacked_size = struct.unpack_from('<I', blob, 2)[0]
        info['packed'] = True
        info['extra'] = 6
        info['unpacked_size'] = unpacked_size
        payload = blob[6:]
        decoded = lzss_unpack(payload, unpacked_size)
        return decoded, info
    elif sig_u32 == 0 or blob[4:8] == b'OggS':
        info['packed'] = False
        info['extra'] = 4
        return blob[4:], info
    else:
        info['packed'] = False
        info['extra'] = 6
        return blob[6:], info


def encode_entry(payload: bytes, packed: bool, extra: int) -> bytes:
    """Re-encode an entry from payload. If packed, LZSS-compress; prepend correct prefix.

    Returns the full entry blob (prefix + body) ready to put in archive.
    """
    if packed:
        body = lzss_pack(payload)
        # 6-byte prefix: signature low u16 = 0x0001, then u32 unpacked_size at offset 2
        # signature u32 = 0xUUUU0001 (low 16 = 1, high 16 = top of unpacked_size)
        # Actually format is: bytes[0..1]=0x0001, bytes[2..5]=unpacked_size u32
        unpacked = len(payload)
        prefix = struct.pack('<HI', 1, unpacked)
        return prefix + body
    else:
        # raw with `extra` byte prefix (we need to preserve original bytes 0..extra-1)
        # caller must pass the prefix separately, or we just emit blank padding
        raise NotImplementedError("encode_entry only handles packed=True; "
                                  "for raw entries, prepend original prefix manually")


if __name__ == '__main__':
    import os, sys
    sys.stdout.reconfigure(encoding='utf-8')
    base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
    snl_path = os.path.join(base, 'sall.snl')

    count, sizes, blobs = read_archive(snl_path)
    print(f"sall.snl: count={count}, nonzero={sum(1 for s in sizes if s and s != 0xFFFFFFFF)}")

    # Decode entry 0
    for idx in [0, 1, 2, 5, 50]:
        if not blobs[idx]:
            print(f"--- entry {idx}: EMPTY")
            continue
        payload, info = decode_entry(blobs[idx])
        print(f"--- entry {idx}: packed={info.get('packed')} extra={info.get('extra')}"
              f" packed_size={len(blobs[idx])} payload={len(payload)} bytes")
        # Look at decompressed bytes
        print(f"    first 64 bytes: {payload[:64].hex()}")
        # Find first Japanese-looking strings
        sjis_strs = []
        i = 0
        while i < min(len(payload), 4096):
            b = payload[i]
            if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
                # try to read run
                start = i
                while i + 1 < len(payload) and (0x81 <= payload[i] <= 0x9F or 0xE0 <= payload[i] <= 0xFC) and 0x40 <= payload[i+1] <= 0xFC and payload[i+1] != 0x7F:
                    i += 2
                if i - start >= 4:
                    try:
                        s = payload[start:i].decode('shift_jis')
                        sjis_strs.append((start, s))
                    except UnicodeDecodeError:
                        pass
            i += 1
        for off, s in sjis_strs[:6]:
            print(f"    @0x{off:04x} {s!r}")
