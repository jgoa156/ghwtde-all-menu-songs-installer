"""Build MenuMusicCollection.exe (one windowed exe) with PyInstaller: python build.py

Output: dist\\MenuMusicCollection.exe (build\\ holds PyInstaller's work files; both are git-ignored).
Then python make_package.py <sources folder> <package parent folder> assembles the release package.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
           '--name', 'MenuMusicCollection', '--distpath', os.path.join(HERE, 'dist'),
           '--workpath', os.path.join(HERE, 'build'), '--specpath', os.path.join(HERE, 'build'),
           '--paths', HERE, os.path.join(HERE, 'MenuMusicCollection.py')]
    subprocess.check_call(cmd, cwd=HERE)
    exe = os.path.join(HERE, 'dist', 'MenuMusicCollection.exe')
    print(f'{exe}: {os.path.getsize(exe) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
