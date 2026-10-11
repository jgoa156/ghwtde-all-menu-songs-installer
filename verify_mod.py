"""Independent check of a built "Main Menu Music Collection" folder (developer tool, not part of the exe).

usage: python verify_mod.py <mod folder> [--sources <sources folder> --games GH5,WoR]

Re-parses the mod with its own small parser (not the installer's) and checks: FSB4 header, sample count = ini Track
count = dat count, every dat key = qbkey(Track) -> sample index, 80-byte sample headers, sample data offsets/lengths
add up to the file size, each sample starts with an MPEG frame, ModInfo text uses only safe characters.  With
--sources it also checks every sample's header and bytes against the selected source (after the merger's renaming)
and that the ini Delay/Volume/Offset values were carried over.
"""
import argparse
import hashlib
import os
import struct
import sys
import zlib

SAFE = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.:/')


def qbkey(s):
    return ~zlib.crc32(s.lower().encode()) & 0xffffffff


def ini_of(path):
    sections, order, cur = {}, [], None
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            cur = line[1:-1]
            sections[cur] = {}
            order.append(cur)
        elif '=' in line and cur is not None:
            k, v = line.split('=', 1)
            sections[cur].setdefault(k, []).append(v)
    return sections


def check(mod, expected=None):
    errs = []

    def need(cond, msg):
        if not cond:
            errs.append(msg)
    ini = ini_of(os.path.join(mod, 'menumusic.ini'))
    info = ini['MenuMusicInfo']
    fsb_name, tracks = info['FSBName'][0], info['Track']
    for k in ('Name', 'Description'):
        need(not set(ini['ModInfo'][k][0]) - SAFE, f'ModInfo {k} has unsafe characters: {ini["ModInfo"][k][0]!r}')
    need(ini['ModInfo']['Author'][0] == 'WitchDoctoR', 'Author')
    fsb = open(os.path.join(mod, 'Content', fsb_name + '.fsb.xen'), 'rb').read()
    dat = open(os.path.join(mod, 'Content', fsb_name + '.dat.xen'), 'rb').read()
    magic, num, shdr, dsize, ver, flags = struct.unpack_from('<4sIIIII', fsb, 0)
    need(magic == b'FSB4', 'magic')
    need(num == len(tracks), f'FSB samples {num} != ini tracks {len(tracks)}')
    count, key = struct.unpack_from('>II', dat, 0)
    need(count == num, f'dat count {count} != FSB samples {num}')
    need(len(dat) == 8 + 20 * count, 'dat length')
    need(key == qbkey(fsb_name), 'dat FSBName key')
    need(shdr == 80 * num, 'sample header block size')
    need(len(fsb) == 48 + shdr + dsize, f'file size {len(fsb)} != {48 + shdr + dsize}')
    need(fsb[24:48] == bytes(24), 'FSB header padding')
    need(all(dat[16 + 20 * k:28 + 20 * k] == bytes(12) for k in range(count)), 'dat padding')
    need(len(set(t.lower() for t in tracks)) == len(tracks), 'duplicate track names')
    need(set(ini) >= set(tracks), 'ini sections for every track')
    off, samples = 48 + shdr, []
    for i in range(num):
        h = fsb[48 + 80 * i:48 + 80 * i + 80]
        nbytes = struct.unpack_from('<I', h, 36)[0]
        mode = struct.unpack_from('<I', h, 48)[0]
        need(struct.unpack_from('<H', h, 0)[0] == 80, f'sample {i} header size')
        data = fsb[off:off + nbytes]
        need(len(data) == nbytes, f'sample {i} runs past the end')
        need(data[:1] == b'\xff' and data[1] & 0xe0 == 0xe0 or data[:3] == b'ID3', f'sample {i} does not start with MPEG data')
        need(mode & 0x200, f'sample {i} mode {mode:#x}')
        samples.append((h, data))
        off += nbytes
    need(off == len(fsb), f'samples end at {off}, file is {len(fsb)}')
    dat_index = {}
    for k in range(count):
        a, b = struct.unpack_from('>II', dat, 8 + 20 * k)
        dat_index[a] = b
    for i, t in enumerate(tracks):
        need(dat_index.get(qbkey(t)) == i, f'dat key of {t} -> {dat_index.get(qbkey(t))}, expected {i}')
    if expected is not None:
        need(len(expected) == num, f'expected {len(expected)} tracks, mod has {num}')
        for i, (clip_name, c) in enumerate(expected[:num]):
            h, data = samples[i]
            need(tracks[i] == clip_name, f'track {i}: {tracks[i]} != {clip_name}')
            with open(c.bank, 'rb') as f:
                f.seek(c.off)
                src = f.read(c.nbytes)
            need(hashlib.sha1(src).digest() == hashlib.sha1(data).digest(), f'{clip_name}: sample bytes differ from the source')
            if clip_name == c.orig_name:
                need(h == c.header, f'{clip_name}: sample header differs from the source')
            else:
                need(h[:2] == c.header[:2] and h[32:] == c.header[32:], f'{clip_name}: renamed header differs beyond the name')
            sec = ini[clip_name]
            need((sec['Delay'][0], sec['Volume'][0], sec['Offset'][0]) == (c.delay, c.volume, c.offset), f'{clip_name}: ini values')
    return errs, dict(tracks=num, bytes=dsize, filesize=len(fsb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mod')
    ap.add_argument('--sources')
    ap.add_argument('--games', default='all')
    a = ap.parse_args()
    expected = None
    if a.sources:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mmc_core as core
        srcs, _ = core.find_sources(a.sources)
        clips, _ = core.plan_tracks(core.select_games(srcs, a.games))
        expected = [(c.name, c) for c in clips]
    errs, info = check(a.mod, expected)
    print(f'{a.mod}: {info["tracks"]} tracks, sample data {info["bytes"]} bytes, FSB file {info["filesize"]} bytes '
          f'({info["filesize"] / 1e6:.1f} MB)')
    for e in errs:
        print('  FAIL:', e)
    print('OK' if not errs else f'{len(errs)} problem(s)')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
