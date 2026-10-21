"""Let the Kindle library show a sideloaded dictionary's own cover.

usage: python3 library_cover.py <file.mobi>...

kindling writes the dictionary's identifier to EXTH 113 and 504, the ASIN
records. A Kindle that finds an ASIN looks the cover up in the Amazon store,
finds nothing, and leaves the library tile blank instead of using the cover
in the file. This renames both records (113 -> 9113, 504 -> 9504) in place,
so no length or offset changes and the firmware skips them as unknown.
Checked on a Kindle: the cover shows, lookups and Vocabulary Builder work.
"""
import struct
import sys

RENAME = {113: 9113, 504: 9504}


def exth_offsets(data):
    """Offsets of the EXTH blocks: record 0's and, in a dual file, the KF8 header's."""
    records = struct.unpack('>H', data[76:78])[0]
    starts = [struct.unpack('>I', data[78 + 8 * n:82 + 8 * n])[0] for n in range(records)]
    headers = [0] + [n + 1 for n in range(records - 1) if data[starts[n]:starts[n] + 8] == b'BOUNDARY']
    for n in headers:
        rec = starts[n]
        if data[rec + 16:rec + 20] == b'MOBI' and struct.unpack('>I', data[rec + 128:rec + 132])[0] & 0x40:
            yield rec + 16 + struct.unpack('>I', data[rec + 20:rec + 24])[0]


for path in sys.argv[1:]:
    data = bytearray(open(path, 'rb').read())
    renamed = 0
    for i in exth_offsets(data):
        assert data[i:i + 4] == b'EXTH'
        count = struct.unpack('>I', data[i + 8:i + 12])[0]
        p = i + 12
        for _ in range(count):
            kind, length = struct.unpack('>II', data[p:p + 8])
            if kind in RENAME:
                data[p:p + 4] = struct.pack('>I', RENAME[kind])
                renamed += 1
            p += length
    open(path, 'wb').write(data)
    print(f'{path}: {renamed} ASIN records renamed')
