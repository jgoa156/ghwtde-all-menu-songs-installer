"""Builds the release zip: dist/GHWoR-Main-Menu-Music_<version>.zip (and a copy in releases/), mirroring the game
folder (extract into the folder with GHWT_Definitive.exe). The mod folder comes from the GH5 / WoR HUD repo's build
(tools/wor_menu_music.py, run by its build.py into build/menu_music): MOD_SRC (env) overrides where."""
import os, shutil

VERSION = '1.0'
MOD_DIR = '(GHWoR) Main Menu Music'
ROOT = os.path.dirname(os.path.abspath(__file__))
MOD_SRC = os.environ.get('MOD_SRC', os.path.join(ROOT, '..', '..', 'ghwt-wor-hud', 'build', 'menu_music', MOD_DIR))

name = f'GHWoR-Main-Menu-Music_{VERSION}'
dist = os.path.join(ROOT, 'dist')
shutil.rmtree(dist, ignore_errors=True)
main = os.path.join(dist, name)
assert os.path.exists(os.path.join(MOD_SRC, 'menumusic.ini')), f'no built mod in {MOD_SRC}'
shutil.copytree(MOD_SRC, os.path.join(main, 'DATA', 'MODS', MOD_DIR))
shutil.copy(os.path.join(ROOT, 'README.txt'), os.path.join(main, 'README - GHWoR Main Menu Music.txt'))
shutil.make_archive(main, 'zip', main)
os.makedirs(os.path.join(ROOT, '..', 'releases'), exist_ok=True)
shutil.copy(main + '.zip', os.path.join(ROOT, '..', 'releases'))   # the repo's releases/
print('packaged', name + '.zip', os.path.getsize(main + '.zip') // 1000000, 'MB')
