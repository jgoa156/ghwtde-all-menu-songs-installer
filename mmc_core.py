"""Core of the GHWT:DE Menu Music Collection installer (no GUI, no third-party modules).

The Guitar Hero World Tour: Definitive Edition loads only ONE menu music mod from DATA\\MODS ("ERROR: Exceeded limit
of 1 menu music mod." in Logs\\debug.txt).  To hear several games' menu music shuffled, their tracks are merged into one
mod.  Each SOURCE is an existing DE menu music mod folder:

  menumusic.ini              [ModInfo] Name/Description/Author/Version, [MenuMusicInfo] FSBName + Track=<name> lines,
                             then one [<name>] section per track with Delay/Volume/Offset
  Content/<FSBName>.dat.xen  big-endian u32 count, u32 qbkey(FSBName), count x {u32 qbkey(track), u32 index, 12 zero bytes}
  Content/<FSBName>.fsb.xen  FSB4 bank: 48-byte header, 80-byte sample headers, MPEG samples back to back

qbkey(s) = ~crc32(s.lower()) & 0xffffffff.  Nothing is decoded or re-encoded: every sample's 80-byte header (sample
rate, channels, loop fields, mode) and MP3 bytes are copied as they are, with the source's ini Delay/Volume/Offset.
If two sources share a track name (case-insensitive) the later one is renamed "<name>_<game code>" everywhere
(ini Track, ini section, dat key, FSB sample name).
"""
import os
import re
import shutil
import struct
import zlib

MOD_DIR = 'Main Menu Music Collection'
FSB_NAME = 'Menu_Music_Collection'     # not displayed, so the underscore is fine
MOD_TITLE = 'Main Menu Music Collection'
AUTHOR = 'WitchDoctoR'
VERSION = '1.0'
# the DE fonts lack " ( ) _ - ; ! & and more: ModInfo Name/Description may only use these
SAFE_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.:/')
BIG_BANK_MB = 300                      # the game is 32-bit and may hold the bank in memory
CHUNK = 1 << 20

# (code, aliases, friendly name, short name for the mod description); order = list order = track order in the mod
GAMES = [
    ('GH1', ('GH1', 'GHI', 'GH'), 'Guitar Hero', 'Guitar Hero'),
    ('GH2', ('GH2', 'GHII'), 'Guitar Hero II', 'Guitar Hero II'),
    ('GH80s', ('GH80S', '80S', 'ENCORE', 'GHE'), 'Guitar Hero Encore: Rocks the 80s', 'Encore Rocks the 80s'),
    ('GHA', ('GHA', 'AEROSMITH'), 'Guitar Hero: Aerosmith', 'Aerosmith'),
    ('GHM', ('GHM', 'METALLICA'), 'Guitar Hero: Metallica', 'Metallica'),
    ('GHSH', ('GHSH', 'SMASHHITS'), 'Guitar Hero: Smash Hits', 'Smash Hits'),
    ('GHVH', ('GHVH', 'VANHALEN'), 'Guitar Hero: Van Halen', 'Van Halen'),
    ('GH5', ('GH5',), 'Guitar Hero 5', 'Guitar Hero 5'),
    ('BH', ('BH', 'BANDHERO'), 'Band Hero', 'Band Hero'),
    ('GHWoR', ('GHWOR', 'WOR', 'GH6', 'WARRIORSOFROCK'), 'Guitar Hero: Warriors of Rock', 'Warriors of Rock'),
]


class MenuMusicError(Exception):
    """A problem to show to the user (bad source, bad game folder, disk full, ...)."""


def norm(s):
    return re.sub(r'[^A-Za-z0-9]', '', s).upper()


def game_for(token):
    """GAMES entry for a folder prefix like 'GH II' or a command line token like 'wor'; None if unknown."""
    t = norm(token)
    for g in GAMES:
        if t == norm(g[0]) or t in g[1]:
            return g
    return None


def qbkey(s):
    return ~zlib.crc32(s.lower().encode()) & 0xffffffff


def read_ini(path):
    """{section: {key: [values]}} (Track repeats); section and key case kept."""
    out, sec = {}, None
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                sec = out.setdefault(line[1:-1], {})
            elif '=' in line and sec is not None and not line.startswith((';', '#')):
                k, v = line.split('=', 1)
                sec.setdefault(k.strip(), []).append(v.strip())
    return out


def ci_get(d, key, default=None):
    """Case-insensitive dict lookup (ini sections: the GHM mod's Track says Kingnothing, its section kingnothing)."""
    if key in d:
        return d[key]
    low = key.lower()
    for k, v in d.items():
        if k.lower() == low:
            return v
    return default


def find_file(folder, name):
    p = os.path.join(folder, name)
    if os.path.isfile(p):
        return p
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.lower() == name.lower():
                return os.path.join(folder, f)
    raise MenuMusicError(f'Missing file: {p}')


def read_fsb(path):
    """FSB4 bank -> dict(num, shdr, dsize, size, samples=[dict(header, name, nsamp, nbytes, mode, freq, chans, off)])."""
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        h = f.read(48)
        if len(h) < 48 or h[:4] != b'FSB4':
            raise MenuMusicError(f'Not an FSB4 bank: {path}')
        num, shdr, dsize = struct.unpack_from('<III', h, 4)
        hdr = f.read(shdr)
    if len(hdr) != shdr:
        raise MenuMusicError(f'Truncated FSB4 header: {path}')
    samples, p, off = [], 0, 48 + shdr
    for _ in range(num):
        if p + 80 > len(hdr):
            raise MenuMusicError(f'Bad FSB4 sample headers: {path}')
        hsize = struct.unpack_from('<H', hdr, p)[0]
        if hsize != 80:
            raise MenuMusicError(f'Unsupported FSB4 sample header size {hsize} in {path}')
        name = hdr[p + 2:p + 32].split(b'\0')[0].decode('latin-1')
        nsamp, nbytes, _, _, mode = struct.unpack_from('<IIIII', hdr, p + 32)
        freq, _, _, _, chans = struct.unpack_from('<iHhHH', hdr, p + 52)
        samples.append(dict(header=hdr[p:p + 80], name=name, nsamp=nsamp, nbytes=nbytes, mode=mode, freq=freq,
                            chans=chans, off=off))
        off += nbytes
        p += hsize
    if size != 48 + shdr + dsize or off != 48 + shdr + dsize:
        raise MenuMusicError(f'FSB4 sizes do not add up (file {size}, header says {48 + shdr + dsize}, '
                             f'samples end at {off}): {path}')
    return dict(num=num, shdr=shdr, dsize=dsize, size=size, samples=samples)


def read_dat(path):
    """dat.xen -> (qbkey of the FSB name, {qbkey(track): index}, count)."""
    with open(path, 'rb') as f:
        dat = f.read()
    if len(dat) < 8:
        raise MenuMusicError(f'Bad dat file: {path}')
    count, fsb_key = struct.unpack_from('>II', dat, 0)
    if len(dat) != 8 + 20 * count:
        raise MenuMusicError(f'dat file length does not match its count ({count}): {path}')
    index = {}
    for k in range(count):
        key, i = struct.unpack_from('>II', dat, 8 + 20 * k)
        if key in index:
            raise MenuMusicError(f'Duplicate key in dat file: {path}')
        index[key] = i
    return fsb_key, index, count


class Clip:
    """One track of a source: where its bytes live, its sample header and its ini values."""

    def __init__(self, name, header, nbytes, nsamp, bank, off, delay, volume, offset):
        self.name, self.header, self.nbytes, self.nsamp = name, header, nbytes, nsamp
        self.bank, self.off = bank, off
        self.delay, self.volume, self.offset = delay, volume, offset
        self.orig_name = name


class Source:
    def __init__(self, folder):
        self.folder = folder
        self.game = None
        self.code = os.path.basename(folder)
        self.name = os.path.basename(folder)
        self.short = self.name
        self.author = ''
        self.clips = []

    @property
    def ntracks(self):
        return len(self.clips)

    @property
    def nbytes(self):
        return sum(c.nbytes for c in self.clips)


def parse_source(folder):
    """Read and validate one DE menu music mod folder (headers only: the MP3 data is read when building)."""
    src = Source(folder)
    m = re.match(r'\s*\((.+?)\)', os.path.basename(folder))
    if m:
        src.game = game_for(m.group(1))
    if src.game:
        src.code, _, src.name, src.short = src.game
    elif m:
        src.code = norm(m.group(1)) or src.code
    ini_path = os.path.join(folder, 'menumusic.ini')
    try:
        ini = read_ini(ini_path)
        info = ci_get(ini, 'MenuMusicInfo')
        if not info or not info.get('FSBName') or not info.get('Track'):
            raise MenuMusicError('menumusic.ini has no [MenuMusicInfo] FSBName/Track')
        fsb_name, tracks = info['FSBName'][0], info['Track']
        src.author = ((ci_get(ini, 'ModInfo') or {}).get('Author') or [''])[0]
        content = os.path.join(folder, 'Content')
        bank = find_file(content, fsb_name + '.fsb.xen')
        fsb_key, index, count = read_dat(find_file(content, fsb_name + '.dat.xen'))
        fsb = read_fsb(bank)
        if fsb_key != qbkey(fsb_name):
            raise MenuMusicError('dat file does not hold the key of the FSBName')
        if not (fsb['num'] == len(tracks) == count):
            raise MenuMusicError(f'sample count {fsb["num"]}, ini Track count {len(tracks)} and dat count {count} '
                                 'are not all equal')
        if len({t.lower() for t in tracks}) != len(tracks):
            raise MenuMusicError('duplicate Track names')
        vols = [ci_get(ini, t, {}).get('Volume', [None])[0] for t in tracks]
        vols = [v for v in vols if v]
        def_vol = max(set(vols), key=vols.count) if vols else '6'
        used = set()
        for t in tracks:
            if re.search(r'[=\[\]\r\n]', t) or not t:
                raise MenuMusicError(f'bad track name {t!r}')
            if qbkey(t) not in index:
                raise MenuMusicError(f'track {t} is missing in the dat file')
            i = index[qbkey(t)]
            if not 0 <= i < fsb['num'] or i in used:
                raise MenuMusicError(f'track {t} has a bad or repeated sample index {i}')
            used.add(i)
            s = fsb['samples'][i]
            if not s['mode'] & 0x200:
                raise MenuMusicError(f'track {t} is not MPEG audio (mode {s["mode"]:#x})')
            sec = ci_get(ini, t, {})
            src.clips.append(Clip(t, s['header'], s['nbytes'], s['nsamp'], bank, s['off'],
                                  sec.get('Delay', ['0.0'])[0], sec.get('Volume', [def_vol])[0],
                                  sec.get('Offset', ['0'])[0]))
    except MenuMusicError as e:
        raise MenuMusicError(f'{os.path.basename(folder)}: {e}') from None
    except (OSError, KeyError, struct.error) as e:
        raise MenuMusicError(f'{os.path.basename(folder)}: {e}') from None
    return src


def find_sources(sources_dir):
    """([Source] in game order, [(folder, error text)]) for every subfolder of sources_dir holding a menumusic.ini."""
    found, problems = [], []
    if os.path.isdir(sources_dir):
        for name in sorted(os.listdir(sources_dir)):
            folder = os.path.join(sources_dir, name)
            if os.path.isfile(os.path.join(folder, 'menumusic.ini')):
                try:
                    found.append(parse_source(folder))
                except MenuMusicError as e:
                    problems.append((folder, str(e)))
    order = {g[0]: i for i, g in enumerate(GAMES)}
    found.sort(key=lambda s: (order.get(s.game[0], len(GAMES)) if s.game else len(GAMES), s.folder.lower()))
    return found, problems


def select_games(sources, spec):
    """Sources named by a comma separated list of codes/aliases ('GH5,WoR'); 'all' or empty selects everything."""
    if not spec or spec.strip().lower() == 'all':
        return list(sources)
    picked = []
    for tok in re.split(r'[,;]', spec):
        if not tok.strip():
            continue
        g = game_for(tok)
        hit = [s for s in sources if (g and s.game == g) or (not g and norm(s.code) == norm(tok))]
        if not hit:
            raise MenuMusicError(f'No source for "{tok.strip()}" (known: ' + ', '.join(s.code for s in sources) + ')')
        for s in hit:
            if s not in picked:
                picked.append(s)
    return [s for s in sources if s in picked]


def plan_tracks(sources):
    """All clips of the selected sources in order, colliding names renamed; returns (clips, [(code, old, new)])."""
    clips, renames, seen = [], [], set()
    for s in sources:
        for c in s.clips:
            c.name = c.orig_name
            if c.name.lower() in seen:
                new = f'{c.orig_name}_{s.code}'
                n = 2
                while new.lower() in seen:
                    new = f'{c.orig_name}_{s.code}{n}'
                    n += 1
                renames.append((s.code, c.orig_name, new))
                c.name = new
            seen.add(c.name.lower())
            clips.append(c)
    return clips, renames


def description_for(sources):
    names = [s.short for s in sources]
    text = f'Main menu music from {len(names)} game{"" if len(names) == 1 else "s"}, shuffled: ' + ', '.join(names) + '.'
    bad = set(text) - SAFE_CHARS
    if bad:
        text = re.sub(r'[^A-Za-z0-9 ,.:/]', '', text)
    return text


def megabytes(n):
    return n / 1e6


def build_mod(parent, sources, progress=None):
    """Write <parent>\\Main Menu Music Collection from the selected sources, replacing an older one.
    progress(fraction 0..1, text) is called while it works.  Returns dict(mod, tracks, bytes, renames)."""
    def report(f, text):
        if progress:
            progress(min(max(f, 0.0), 1.0), text)

    if not sources:
        raise MenuMusicError('Tick at least one game.')
    clips, renames = plan_tracks(sources)
    title, desc = MOD_TITLE, description_for(sources)
    for text in (title, desc):
        if set(text) - SAFE_CHARS:
            raise MenuMusicError(f'Characters the game fonts lack in {text!r}')
    total = sum(c.nbytes for c in clips)
    try:
        os.makedirs(parent, exist_ok=True)
        free = shutil.disk_usage(parent).free
    except OSError as e:
        raise MenuMusicError(f'Cannot use the folder {parent}: {e}') from None
    if free < total + (64 << 20):
        raise MenuMusicError(f'Not enough free disk space in {parent}: need about {megabytes(total):.0f} MB, '
                             f'have {megabytes(free):.0f} MB.')
    final = os.path.join(parent, MOD_DIR)
    tmp = final + '.building'
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        os.makedirs(os.path.join(tmp, 'Content'))
        report(0.0, 'Writing the sound bank...')
        # FSB4: 48-byte header, the sources' own 80-byte sample headers (name rewritten only for renamed tracks), data
        shdrs = b''
        for c in clips:
            h = c.header
            if c.name != c.orig_name:
                h = h[:2] + struct.pack('<30s', (c.name + '.mp3').encode('latin-1', 'replace')[:29]) + h[32:]
            shdrs += h
        done, handles = 0, {}
        try:
            with open(os.path.join(tmp, 'Content', FSB_NAME + '.fsb.xen'), 'wb') as out:
                out.write(struct.pack('<4sIIIII', b'FSB4', len(clips), len(shdrs), total, 0x40000, 0) + bytes(24) + shdrs)
                for c in clips:
                    f = handles.get(c.bank)
                    if f is None:
                        f = handles[c.bank] = open(c.bank, 'rb')
                    f.seek(c.off)
                    left = c.nbytes
                    while left:
                        data = f.read(min(CHUNK, left))
                        if not data:
                            raise MenuMusicError(f'Unexpected end of {os.path.basename(c.bank)}')
                        out.write(data)
                        left -= len(data)
                        done += len(data)
                        report(0.95 * done / max(total, 1), f'Copying {c.name}')
        finally:
            for f in handles.values():
                f.close()
        dat = struct.pack('>II', len(clips), qbkey(FSB_NAME)) + b''.join(
            struct.pack('>II', qbkey(c.name), i) + bytes(12) for i, c in enumerate(clips))
        with open(os.path.join(tmp, 'Content', FSB_NAME + '.dat.xen'), 'wb') as f:
            f.write(dat)
        ini = ['[ModInfo]', f'Name={title}', f'Description={desc}', f'Author={AUTHOR}', f'Version={VERSION}', '',
               '[MenuMusicInfo]', f'FSBName={FSB_NAME}']
        ini += [f'Track={c.name}' for c in clips] + ['']
        for c in clips:
            ini += [f'[{c.name}]', f'Delay={c.delay}', f'Volume={c.volume}', f'Offset={c.offset}', '']
        report(0.96, 'Checking the result...')
        # the ini goes in last, so an interrupted build never leaves a loadable half mod behind
        with open(os.path.join(tmp, 'menumusic.ini'), 'w', newline='\r\n', encoding='utf-8') as f:
            f.write('\n'.join(ini))
        validate_mod(tmp)
        report(0.98, 'Replacing the older collection...')
        if os.path.isdir(final):
            shutil.rmtree(final)
        os.replace(tmp, final)
    except MenuMusicError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    except OSError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise MenuMusicError(f'Could not write {final}: {e}') from None
    report(1.0, 'Done')
    return dict(mod=final, tracks=len(clips), bytes=total, renames=renames)


def validate_mod(mod):
    """Re-parse a built mod: FSB sample count = ini tracks = dat count, every dat key = qbkey(Track), sizes consistent.
    Returns dict(tracks, bytes); raises MenuMusicError."""
    ini = read_ini(os.path.join(mod, 'menumusic.ini'))
    info = ini['MenuMusicInfo']
    fsb_name, tracks = info['FSBName'][0], info['Track']
    for key in ('Name', 'Description'):
        if set(ini['ModInfo'][key][0]) - SAFE_CHARS:
            raise MenuMusicError(f'ModInfo {key} has characters the game fonts lack')
    fsb = read_fsb(find_file(os.path.join(mod, 'Content'), fsb_name + '.fsb.xen'))
    fsb_key, index, count = read_dat(find_file(os.path.join(mod, 'Content'), fsb_name + '.dat.xen'))
    if not (fsb['num'] == len(tracks) == count):
        raise MenuMusicError(f'sample count {fsb["num"]}, ini Track count {len(tracks)}, dat count {count} differ')
    if fsb_key != qbkey(fsb_name):
        raise MenuMusicError('dat FSBName key mismatch')
    for i, t in enumerate(tracks):
        if index.get(qbkey(t)) != i:
            raise MenuMusicError(f'dat key of track {t} does not point at sample {i}')
        if ci_get(ini, t) is None:
            raise MenuMusicError(f'ini has no section for track {t}')
    return dict(tracks=len(tracks), bytes=fsb['dsize'])


# ---- game folder and other menu music mods

def is_game_dir(p):
    return os.path.isfile(os.path.join(p, 'GHWT_Definitive.exe'))


def detect_game_dir(start):
    """The folder of GHWT_Definitive.exe: start or one of its parents, else Steam's default library; '' if none."""
    p = os.path.abspath(start)
    while True:
        if is_game_dir(p):
            return p
        up = os.path.dirname(p)
        if up == p:
            break
        p = up
    libs = []
    roots = [os.path.join(r, 'Steam') for r in
             (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), r'C:\Program Files (x86)') if r]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
            roots.append(os.path.normpath(winreg.QueryValueEx(k, 'SteamPath')[0]))
    except (ImportError, OSError):
        pass
    for steam in roots:
        if os.path.isdir(os.path.join(steam, 'steamapps')) and steam not in libs:
            libs.append(steam)
            try:
                with open(os.path.join(steam, 'steamapps', 'libraryfolders.vdf'), encoding='utf-8',
                          errors='replace') as f:
                    for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                        lib = m.group(1).replace('\\\\', '\\')
                        if lib not in libs:
                            libs.append(lib)
            except OSError:
                pass
    for lib in libs:
        common = os.path.join(lib, 'steamapps', 'common')
        guess = os.path.join(common, 'Guitar Hero World Tour')
        if is_game_dir(guess):
            return guess
        try:
            for d in os.listdir(common):
                if is_game_dir(os.path.join(common, d)):
                    return os.path.join(common, d)
        except OSError:
            pass
        if os.path.isdir(guess):
            return guess
    return ''


def mods_dir(game):
    return os.path.join(game, 'DATA', 'MODS')


def check_game_dir(game):
    """Raise MenuMusicError unless game looks like a game folder; returns DATA\\MODS (created if missing)."""
    if not game or not os.path.isdir(game):
        raise MenuMusicError('Choose the game folder (the one with GHWT_Definitive.exe).')
    if not os.path.isdir(os.path.join(game, 'DATA')):
        raise MenuMusicError(f'There is no DATA folder in {game}.\nChoose the folder that holds GHWT_Definitive.exe.')
    return mods_dir(game)


def find_other_menu_mods(mods, exclude=MOD_DIR):
    """Folders in DATA\\MODS (other than ours) that hold an active menumusic.ini."""
    out = []
    if os.path.isdir(mods):
        for d in sorted(os.listdir(mods), key=str.lower):
            p = os.path.join(mods, d)
            if d.lower() != exclude.lower() and not d.lower().endswith('.building') \
                    and os.path.isfile(os.path.join(p, 'menumusic.ini')):
                out.append(p)
    return out


def disable_menu_mod(folder):
    """Rename the folder's menumusic.ini to menumusic.ini.disabled (never deletes); returns the new path."""
    src = os.path.join(folder, 'menumusic.ini')
    dst = src + '.disabled'
    n = 1
    while os.path.exists(dst):
        n += 1
        dst = f'{src}.disabled{n}'
    os.rename(src, dst)
    return dst
