#!/usr/bin/env python3
"""Reduce an iOS restore disk image to its raw APFS container.

Apple's current CDN serves the OS image of older IPSWs as an lzfse stream;
after decompression the result is either a bare APFS container (checksum +
NXSB at 0x20) or a GPT disk image whose APFS partition holds it, possibly
with a trailing UDIF koly trailer (empty resource fork = "wrapped" marker,
not a real UDIF). This script rewrites its input in place to a file that
starts at the container superblock, so apfs-fuse can mount it like the
cryptex images.
"""
import os
import struct
import sys

# APFS partition type GUID as stored in a GPT entry (mixed endian)
APFS_TYPE_GUID = bytes.fromhex('ef57347c0000aa11aa1100306543ecac')


def is_apfs(head):
    """A bare APFS container starts with an 8-byte fletcher checksum and a
    32-byte object header; the NXSB magic sits at 0x20. The checksum value
    differs per container - only the magic position is invariant."""
    return len(head) >= 36 and head[0x20:0x24] == b'NXSB'


def main(src):
    size = os.path.getsize(src)
    f = open(src, 'rb')
    head = f.read(64)
    if is_apfs(head):
        print('already a bare APFS container')
    else:
        f.seek(512)
        gpt = f.read(512)
        if gpt[:8] != b'EFI PART':
            raise SystemExit(f'{src}: neither raw APFS (head {head[:4].hex()}) '
                             f'nor a GPT disk ({gpt[:8]!r})')
        pe_lba, = struct.unpack_from('<Q', gpt, 72)
        nent, esz = struct.unpack_from('<II', gpt, 80)
        f.seek(pe_lba * 512)
        entries = f.read(nent * esz)
        apfs_off = None
        for i in range(nent):
            e = entries[i * esz:(i + 1) * esz]
            if e[:16] == APFS_TYPE_GUID:
                first, = struct.unpack_from('<Q', e, 32)
                apfs_off = first * 512
                break
        if apfs_off is None:
            raise SystemExit('no APFS partition in the GPT')
        print(f'APFS partition at byte offset {apfs_off} (LBA {apfs_off // 512})')
        f.seek(apfs_off)
        out = src + '.apfs'
        with open(out, 'wb') as o:
            while True:
                b = f.read(1 << 22)
                if not b:
                    break
                o.write(b)
        f.close()
        os.replace(out, src)
        size = os.path.getsize(src)
        f = open(src, 'rb')
    f.seek(size - 512)
    tail = f.read(512)
    if tail[-4:] == b'koly':
        _, rsrc_len = struct.unpack_from('>QQ', tail, 0x28)
        if rsrc_len == 0:
            f.close()
            with open(src, 'r+b') as g:
                g.truncate(size - 512)
            print(f'stripped empty-fork koly trailer, {size - 512} bytes left')
            size -= 512
        else:
            print(f'real UDIF (resource fork {rsrc_len} bytes) - leaving as is')
    f.close()
    with open(src, 'rb') as g:
        head = g.read(64)
        if not is_apfs(head):
            raise SystemExit(f'{src}: final head is not a raw APFS container '
                             f'({head[:36].hex()})')
    print(f'OK: {src} is a raw APFS container ({size} bytes)')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
