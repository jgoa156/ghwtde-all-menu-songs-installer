"""Assemble the release package: python make_package.py <sources folder> <package parent folder>

Creates <parent>\\GHWTDE-Menu-Music-Collection-Installer_1.0\\ (MenuMusicCollection.exe, sources\\, README.txt) and
<parent>\\GHWTDE-Menu-Music-Collection-Installer_1.0.zip.  Run build.py first.
"""
import os
import shutil
import sys
import json
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mmc_core as core  # noqa: E402
import mmc_level  # noqa: E402

NAME = 'GHWTDE-Menu-Music-Collection-Installer_1.0'


def readme(sources):
    lines = [
        'GHWT:DE Menu Music Collection 1.0',
        '=================================',
        '',
        'WHAT IT DOES',
        'Guitar Hero World Tour: Definitive Edition loads only ONE menu music mod from DATA\\MODS (a second one gives',
        '"ERROR: Exceeded limit of 1 menu music mod." in Logs\\debug.txt). To hear the menu songs of several games',
        'shuffled, they have to live in one mod. This program merges the games you tick into a single mod called',
        '"Main Menu Music Collection" and puts it in DATA\\MODS. Nothing is converted or re-encoded. The games\' menu',
        'songs differ in loudness by up to 8 dB, so each track is levelled to about '
        f'{mmc_level.TARGET_LUFS:.0f} LUFS the lossless way',
        '(mp3gain\'s method: each MP3 frame\'s gain field moves in 1.5 dB steps; the audio data is not touched).',
        '',
        'INSTALL',
        '1. Extract this whole folder anywhere (or into your game folder, next to GHWT_Definitive.exe).',
        '   Keep the "sources" folder next to MenuMusicCollection.exe.',
        '2. Run MenuMusicCollection.exe.',
        '3. Check the game folder (the one with GHWT_Definitive.exe). It is found automatically when the program is',
        '   inside the game folder or in the default Steam library; otherwise use Browse.',
        '4. Tick the games whose menu music you want (Select all / Select none help).',
        '5. Click Build. Run it again any time to change the selection: an older collection is replaced.',
        '',
        'ONE MENU MUSIC MOD LOADS',
        'After building, the program lists any OTHER menu music mods in DATA\\MODS (folders with a menumusic.ini) and',
        'offers to disable them. Disabling renames their menumusic.ini to menumusic.ini.disabled; nothing is deleted.',
        'To get one back, rename the file to menumusic.ini and disable the collection instead.',
        '',
        'SIZE',
        'The game is a 32-bit program and may keep the whole sound bank in memory. All ten games together are about',
        f'{core.megabytes(sum(s.nbytes for s in sources)):.0f} MB. The program warns when the selection is over {core.BIG_BANK_MB} MB; if the game',
        'crashes or starts slowly, untick a few games and build again.',
        '',
        'GAMES IN THIS PACKAGE',
    ]
    for s in sources:
        lines.append(f'  {s.name:36s} {s.ntracks:3d} tracks  {core.megabytes(s.nbytes):6.1f} MB')
    lines += [
        '',
        'COMMAND LINE (for testing)',
        '  MenuMusicCollection.exe --game "<game folder>" --games GH5,WoR [--disable-others]',
        '  MenuMusicCollection.exe --out "<folder>" --games GH5,WoR     (builds into a folder, no game needed)',
        '  Game codes: GH1, GH2, GH80s, GHA, GHM, GHSH, GHVH, GH5, BH, WoR (default: all). Add --log <file> to keep',
        '  the output; --list shows the games found.',
        '',
        'CREDITS',
    ]
    by_author = {}
    for s in sources:
        by_author.setdefault(s.author or 'unknown', []).append(s.name)
    for author, names in by_author.items():
        lines.append(f'  Menu music mod(s) by {author}: ' + ', '.join(names))
    lines += [
        '  Installer and the merged "Main Menu Music Collection" mod: WitchDoctoR.',
        '  The songs belong to their owners; this is a fan tool and is not affiliated with anyone.',
        '',
    ]
    text = '\r\n'.join(lines)
    text.encode('ascii')
    return text


def measure_levels(sources):
    """{source folder: {track: gain steps}}: each track's integrated loudness (EBU R128) and sample peak, by ffmpeg."""
    levels = {}
    for s in sources:
        lv = {}
        for c in s.clips:
            with open(c.bank, 'rb') as f:
                f.seek(c.off)
                data = f.read(c.nbytes)
            r = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-f', 'mp3', '-i', 'pipe:0',
                                '-af', 'ebur128=framelog=quiet:peak=sample', '-f', 'null', '-'],
                               input=data, capture_output=True)
            err = r.stderr.decode(errors='replace').splitlines()
            lufs = float([l for l in err if l.strip().startswith('I:')][-1].split()[1])
            peak = float([l for l in err if l.strip().startswith('Peak:')][-1].split()[1])
            lv[c.name] = mmc_level.steps_for(lufs, peak)
            print(f'  {s.code:6s} {c.name:30s} {lufs:6.1f} LUFS  peak {peak:5.1f} dB  -> {lv[c.name] * mmc_level.STEP_DB:+.1f} dB')
        levels[os.path.basename(s.folder)] = lv
    return levels


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sources_dir, parent = sys.argv[1], sys.argv[2]
    exe = os.path.join(HERE, 'dist', 'MenuMusicCollection.exe')
    if not os.path.isfile(exe):
        sys.exit('Run build.py first.')
    sources, problems = core.find_sources(sources_dir)
    if problems or not sources:
        sys.exit(f'Bad sources: {problems}')
    pkg = os.path.join(parent, NAME)
    shutil.rmtree(pkg, ignore_errors=True)
    os.makedirs(pkg)
    shutil.copy2(exe, pkg)
    for s in sources:
        shutil.copytree(s.folder, os.path.join(pkg, 'sources', os.path.basename(s.folder)))
    levels = measure_levels(sources)
    for folder in (sources_dir, os.path.join(pkg, 'sources')):
        with open(os.path.join(folder, mmc_level.LEVELS_FILE), 'w', encoding='utf-8') as f:
            json.dump(levels, f, indent=1)
    with open(os.path.join(pkg, 'README.txt'), 'w', newline='') as f:
        f.write(readme(sources))
    zpath = pkg + '.zip'
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _, files in os.walk(pkg):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.join(NAME, os.path.relpath(p, pkg)))
    print(pkg)
    print(f'{zpath}: {os.path.getsize(zpath) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
