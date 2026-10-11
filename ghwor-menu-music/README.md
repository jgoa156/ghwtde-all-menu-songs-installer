# GHWoR Main Menu Music (v1.0)

The main menu music of **Guitar Hero: Warriors of Rock** for **Guitar Hero World Tour: Definitive Edition**: all 14
songs WoR plays in its menus, shuffled by the game like its own menu music. By **WitchDoctoR**.

**Download:** [`releases/GHWoR-Main-Menu-Music_1.0.zip`](../releases/GHWoR-Main-Menu-Music_1.0.zip). Install
instructions are in the zip's README. It is also one of the games the
[All Menu Songs Installer](../README.md) merges.

Bodies, Jet City Woman, Chemical Warfare, Bloodlines, Ravenous, Hard to See, Waidmanns Heil, Holy Wars... The
Punishment Due, I'm Broken, Indians, Psychosocial, Re-Ignition, The Outsider, Children of the Grave.

**The game loads one menu music mod.** With another one installed (e.g. the GH5 menu music mod), only one of them
plays.

## How it was made

WoR keeps its menu songs in `data/streams/streamall.fsb.xen`: an Xbox 360 FSB4 bank of XMA streams, indexed by
`streamall.dat.xen`, played from the `menu_music_songs` list (`gh6_mm_*`, in
`scripts/game/audio/global_sound_definitions.qb`). Each clip is wrapped as an XMA2 RIFF, decoded with ffmpeg,
brought to -10 LUFS with a peak limiter (WoR mixes its streams about 12 dB quieter than the other menu music mods)
and encoded to 48 kHz stereo MP3 (LAME V4, ~165 kb/s).

A GHWT:DE menu music mod is:

```
menumusic.ini                 [ModInfo]; [MenuMusicInfo] FSBName + Track=<name> lines; one [<name>] Delay/Volume/Offset each
Content/<FSBName>.dat.xen     big-endian: u32 count, u32 qbkey(FSBName), count x {u32 qbkey(track), u32 index, 12 zero bytes}
Content/<FSBName>.fsb.xen     FSB4, 80-byte sample headers, MPEG (mode 0x220), data back to back
```

The tool is `tools/wor_menu_music.py` in the
[GH5 / WoR HUD mod repo](https://github.com/jgoa156/ghwtde-gh5wor-hud-mod) (it needs your own WoR copy and ffmpeg).
To hear several games' menu songs shuffled together, use the [installer](../README.md) in this repo.

```
python tools/wor_menu_music.py <out>   (HUD repo)  -> <out>/(GHWoR) Main Menu Music
python ghwor-menu-music/package.py     (this repo) -> ghwor-menu-music/dist/ and releases/GHWoR-Main-Menu-Music_<version>.zip
```

Songs and recordings belong to their owners; the audio comes from Guitar Hero: Warriors of Rock (Neversoft /
Activision). Own the game.
