#!/usr/bin/env python3
"""Decode Apple's segmented-lzfse disk images.

The lzfse-compressed restore images on Apple's CDN are not one lzfse stream:
they are many independent streams back to back, each ending with the bvx$
end-of-stream marker (the reference lzfse CLI therefore stops after the first
tiny segment). This script splits at bvx$ markers that are followed by a
valid block magic (or EOF), decodes every segment, and writes the
concatenated result. A bvx$ match inside compressed payload data would make
its segment fail to decode; such a segment is merged with the next one and
retried until the stream ends.
"""
import os
import sys

try:
    import liblzfse
except ImportError:
    raise SystemExit('pyliblzfse is required: pip install pyliblzfse')

MAGICS = (b'bvx1', b'bvx2', b'bvxn')


def boundaries(data):
    pts = []
    i = 0
    while True:
        i = data.find(b'bvx$', i)
        if i < 0:
            break
        nxt = data[i + 4:i + 8]
        if nxt == b'' or nxt in MAGICS:
            pts.append(i + 4)
        i += 4
    return pts


def main(src, dst):
    data = open(src, 'rb').read()
    if data[:4] not in MAGICS:
        raise SystemExit(f'{src}: does not start with an lzfse block magic '
                         f'({data[:4].hex()}) - nothing to decode')
    starts = [0] + boundaries(data)
    print(f'{len(starts) - 1} stream boundary candidates')
    out = open(dst, 'wb')
    total = 0
    segs = 0
    i = 0
    while i < len(starts):
        s = starts[i]
        e = starts[i + 1] if i + 1 < len(starts) else len(data)
        seg = data[s:e]
        try:
            dec = liblzfse.decompress(seg)
        except Exception as ex:
            if i + 1 < len(starts):
                print(f'segment {i} ({e - s} B) failed ({ex}); merging with next')
                starts.pop(i + 1)
                continue
            raise
        out.write(dec)
        total += len(dec)
        segs += 1
        i += 1
    out.close()
    print(f'{segs} segments decoded, {total} bytes -> {dst}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
