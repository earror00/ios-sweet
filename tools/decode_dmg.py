#!/usr/bin/env python3
"""Decode Apple's compressed restore disk image (the lzfse-compressed OS dmg
the current CDN serves for older IPSWs).

The file is a UDIF variant: the tail holds an XML resource plist whose blkx
resources describe disk RANGES (MBR, GPT header/table, the APFS partition,
backup GPT), each with a mish chunk table. Chunks are 2048-sector (1 MiB)
pieces stored at absolute file offsets compOff/compLen, either as an
independent lzfse stream (type 0x80000007) or raw (type 0x1). Everything is
placed at sector*512, so the output is the plain disk image.
"""
import mmap
import plistlib
import struct
import sys

try:
    import liblzfse
except ImportError:
    raise SystemExit('pyliblzfse is required: pip install pyliblzfse')

LZFSE_CHUNK = 0x80000007
RAW_CHUNK = 0x1
ZERO_CHUNK = 0x2
END = 0xFFFFFFFF


def main(src, dst):
    f = open(src, 'rb')
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    n = len(mm)

    tail_off = max(0, n - 512 * 1024)
    x = mm.rfind(b'<?xml', tail_off)
    if x < 0:
        raise SystemExit('no XML resource plist in the tail - already uncompressed?')
    plist_bytes = mm[x:n]
    plist_bytes = plist_bytes[:plist_bytes.rfind(b'</plist>') + 8]
    pl = plistlib.loads(bytes(plist_bytes))
    ranges = pl['resource-fork']['blkx']

    total_sectors = 0
    plan = []
    for entry in ranges:
        data = entry['Data']
        if data[:4] != b'mish':
            raise SystemExit(f"range {entry.get('Name')}: Data is not mish")
        range_start, = struct.unpack_from('>Q', data, 8)
        num, = struct.unpack_from('>I', data, 0x0c8)
        for c in range(num):
            o = 0x0cc + 40 * c
            ctype, = struct.unpack_from('>I', data, o)
            sec, cnt, coff, clen = struct.unpack_from('>QQQQ', data, o + 8)
            if ctype == END:
                break
            # chunk sector numbers are relative to the range start
            plan.append((entry.get('Name'), ctype, range_start + sec, cnt, coff, clen))
            total_sectors = max(total_sectors, range_start + sec + cnt)
    print(f'{len(ranges)} ranges, {len(plan)} chunks, disk = {total_sectors} sectors '
          f'({total_sectors * 512 / 2**30:.2f} GiB)')

    out = open(dst, 'wb')
    out.truncate(total_sectors * 512)
    bad = 0
    for i, (name, ctype, sec, cnt, coff, clen) in enumerate(plan):
        data = mm[coff:coff + clen]
        if ctype == LZFSE_CHUNK:
            dec = liblzfse.decompress(bytes(data))
        elif ctype == RAW_CHUNK:
            dec = data
        elif ctype == ZERO_CHUNK:
            dec = b'\0' * (cnt * 512)
        else:
            raise SystemExit(f'chunk {i} ({name}): unknown type {hex(ctype)}')
        if len(dec) != cnt * 512:
            bad += 1
            print(f'chunk {i} ({name}): decoded {len(dec)} bytes, expected {cnt * 512}')
        out.seek(sec * 512)
        out.write(dec)
        if (i + 1) % 500 == 0:
            print(f'{i + 1}/{len(plan)} chunks')
    out.close()
    mm.close()
    f.close()
    if bad:
        raise SystemExit(f'{bad} chunks decoded to the wrong size')
    print(f'OK: {dst} = {total_sectors * 512} bytes, all {len(plan)} chunks verified')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
