"""Deep analysis of Ail .dat archive structure - multi-hypothesis test."""
import os
import struct

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"

def magic_name(b):
    if b[:8] == b'\x89PNG\r\n\x1a\n': return 'PNG'
    if b[:3] == b'BM\x18' or b[:2] == b'BM': return 'BMP'
    if b[:4] == b'RIFF': return 'RIFF/WAV'
    if b[:3] == b'OGG' or b[:4] == b'OggS': return 'OGG'
    if b[:2] == b'\xff\xd8': return 'JPG'
    if b[:4] == b'JFIF': return 'JFIF'
    if b[:3] == b'ID3' or b[:2] == b'\xff\xfb': return 'MP3'
    return f'unk:{b[:8].hex()}'

def test_simple(path):
    """Format: u32 count, u32 size[count], data concatenated."""
    sz = os.path.getsize(path)
    with open(path, 'rb') as f:
        data = f.read()
    count = struct.unpack_from('<I', data, 0)[0]
    if count == 0 or count > 100000: return None
    sizes = list(struct.unpack_from(f'<{count}I', data, 4))
    hdr_end = 4 + count*4
    total = hdr_end + sum(sizes)
    return {
        'count': count,
        'hdr_end': hdr_end,
        'sum_sizes': sum(sizes),
        'expected_total': total,
        'actual_size': sz,
        'matches': total == sz,
        'nonzero_count': sum(1 for s in sizes if s > 0),
        'first10_sizes': sizes[:10],
        'data': data,
        'sizes': sizes,
    }

def test_dump_first_files(path, info):
    """Dump first few files using simple-format hypothesis and check magic."""
    data = info['data']
    sizes = info['sizes']
    off = info['hdr_end']
    out = []
    nfiles = 0
    for i, s in enumerate(sizes):
        if s == 0:
            out.append((i, 0, ''))
            continue
        if nfiles >= 5: break
        chunk = data[off:off+min(s, 16)]
        out.append((i, s, magic_name(chunk)))
        off += s
        nfiles += 1
    return out

archives = ['sall.snl', 'Gall0.dat', 'Pall0.dat', 'Pall1.dat', 'Pall2.dat',
            'vall00.dat', 'vall01.dat', 'THelp.dat']

for name in archives:
    p = os.path.join(base, name)
    info = test_simple(p)
    print(f"=== {name} ({info['actual_size']:,d} bytes)")
    print(f"  count={info['count']}  nonzero={info['nonzero_count']}")
    print(f"  hdr_end={info['hdr_end']}  sum_sizes={info['sum_sizes']:,d}  expected={info['expected_total']:,d}  match={info['matches']}")
    if info['matches']:
        first = test_dump_first_files(p, info)
        for i, s, mg in first:
            print(f"    [{i}] size={s:>10,d}  magic={mg}")
    print()
