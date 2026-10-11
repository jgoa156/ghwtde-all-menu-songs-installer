# GHWT:DE All Menu Songs Installer (Menu Music Collection 1.0)

By WitchDoctoR. Merges the menu music of the Guitar Hero games you tick into ONE menu music mod for
*Guitar Hero World Tour: Definitive Edition* (the DE loads only one).

**Status:** source here; the 1.0 package (exe + the merged games' menu music, ~300 MB) is not published yet: it is
too big for a git commit (GitHub's 100 MB file limit) and it bundles other modders' menu music mods (credits below),
so it waits for a GitHub Release and the authors' blessing. Build it yourself with `build.bat` + `make_package.py`.

```
WHAT IT DOES
Guitar Hero World Tour: Definitive Edition loads only ONE menu music mod from DATA\MODS (a second one gives
"ERROR: Exceeded limit of 1 menu music mod." in Logs\debug.txt). To hear the menu songs of several games
shuffled, they have to live in one mod. This program merges the games you tick into a single mod called
"Main Menu Music Collection" and puts it in DATA\MODS. Nothing is converted or re-encoded: the songs are
copied exactly as the original menu music mods have them.

INSTALL
1. Extract this whole folder anywhere (or into your game folder, next to GHWT_Definitive.exe).
   Keep the "sources" folder next to MenuMusicCollection.exe.
2. Run MenuMusicCollection.exe.
3. Check the game folder (the one with GHWT_Definitive.exe). It is found automatically when the program is
   inside the game folder or in the default Steam library; otherwise use Browse.
4. Tick the games whose menu music you want (Select all / Select none help).
5. Click Build. Run it again any time to change the selection: an older collection is replaced.

ONE MENU MUSIC MOD LOADS
After building, the program lists any OTHER menu music mods in DATA\MODS (folders with a menumusic.ini) and
offers to disable them. Disabling renames their menumusic.ini to menumusic.ini.disabled; nothing is deleted.
To get one back, rename the file to menumusic.ini and disable the collection instead.

SIZE
The game is a 32-bit program and may keep the whole sound bank in memory. All ten games together are about
302 MB. The program warns when the selection is over 300 MB; if the game
crashes or starts slowly, untick a few games and build again.

GAMES IN THIS PACKAGE
  Guitar Hero                           10 tracks    13.2 MB
  Guitar Hero II                        10 tracks    10.8 MB
  Guitar Hero Encore: Rocks the 80s      7 tracks    11.1 MB
  Guitar Hero: Aerosmith                 6 tracks     9.7 MB
  Guitar Hero: Metallica                 9 tracks    21.2 MB
  Guitar Hero: Smash Hits                8 tracks    20.7 MB
  Guitar Hero: Van Halen                 9 tracks    30.6 MB
  Guitar Hero 5                          8 tracks    51.4 MB
  Band Hero                             18 tracks    60.7 MB
  Guitar Hero: Warriors of Rock         14 tracks    73.0 MB

COMMAND LINE (for testing)
  MenuMusicCollection.exe --game "<game folder>" --games GH5,WoR [--disable-others]
  MenuMusicCollection.exe --out "<folder>" --games GH5,WoR     (builds into a folder, no game needed)
  Game codes: GH1, GH2, GH80s, GHA, GHM, GHSH, GHVH, GH5, BH, WoR (default: all). Add --log <file> to keep
  the output; --list shows the games found.

CREDITS
  Menu music mod(s) by Raccoon_333: Guitar Hero, Guitar Hero II, Guitar Hero Encore: Rocks the 80s, Guitar Hero: Aerosmith, Guitar Hero: Metallica, Guitar Hero: Smash Hits, Guitar Hero: Van Halen, Guitar Hero 5, Band Hero
  Menu music mod(s) by WitchDoctoR: Guitar Hero: Warriors of Rock
  Installer and the merged "Main Menu Music Collection" mod: WitchDoctoR.
  The songs belong to their owners; this is a fan tool and is not affiliated with anyone.
```
