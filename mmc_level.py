"""Loudness levelling without re-encoding (the method of mp3gain): every MP3 frame's global_gain fields move by the
same number of steps (1.5 dB each), so the audio data is untouched and the change is lossless and exact.

The steps per track are measured once when the package is made (make_package.py, needs ffmpeg) and stored in
<sources>/mmc_levels.json; the installer applies them while it copies the tracks."""
import json
import os

LEVELS_FILE = 'mmc_levels.json'
TARGET_LUFS = -13.0          # the quietest games' level (Band Hero, Van Halen): the loud ones come down (boosting the
                             # quiet ones would clip: they peak at full scale)
STEP_DB = 1.5                # one global_gain step
HEADROOM_DB = -0.3           # a boost never takes a track's sample peak above this

_BITRATES = {  # (version id, layer III) -> kbit/s by index
    3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],      # MPEG-1
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],           # MPEG-2
    0: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],           # MPEG-2.5
}
_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _frame(data, i):
    """(frame length, side-info start, MPEG-1?, channels) of the layer III frame at i, or None."""
    if i + 4 > len(data) or data[i] != 0xFF or data[i + 1] & 0xE0 != 0xE0:
        return None
    ver = (data[i + 1] >> 3) & 3
    layer = (data[i + 1] >> 1) & 3
    crc = not (data[i + 1] & 1)
    bri = data[i + 2] >> 4
    sri = (data[i + 2] >> 2) & 3
    pad = (data[i + 2] >> 1) & 1
    mode = data[i + 3] >> 6
    if ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:
        return None
    mpeg1 = ver == 3
    length = (144 if mpeg1 else 72) * _BITRATES[ver][bri] * 1000 // _RATES[ver][sri] + pad
    return length, i + 4 + (2 if crc else 0), mpeg1, 1 if mode == 3 else 2


def _gain_bit_offsets(mpeg1, nch):
    """Bit offsets of every global_gain field from the start of the side information."""
    if mpeg1:
        pos = 9 + (5 if nch == 1 else 3) + 4 * nch          # main_data_begin, private bits, scfsi
        grans, block = 2, 59
    else:
        pos = 8 + (1 if nch == 1 else 2)
        grans, block = 1, 63
    out = []
    for _ in range(grans):
        for _ in range(nch):
            out.append(pos + 21)                              # part2_3_length 12 + big_values 9
            pos += block
    return out


def apply_gain(data, steps):
    """The MP3 bytes with every frame's global_gain moved by `steps` (clamped to 0..255). Bytes that are not layer III
    frames (tags, junk) are left as they are."""
    if not steps:
        return data
    b = bytearray(data)
    i = 0
    while i + 4 <= len(b):
        f = _frame(b, i)
        if not f or f[0] < 8:
            i += 1
            continue
        length, side, mpeg1, nch = f
        for bit in _gain_bit_offsets(mpeg1, nch):
            p = side * 8 + bit
            byte, sh = divmod(p, 8)
            if byte + 1 >= len(b):
                break
            word = (b[byte] << 8) | b[byte + 1]
            g = (word >> (8 - sh)) & 0xFF
            g = max(0, min(255, g + steps))
            word = (word & ~(0xFF << (8 - sh)) & 0xFFFF) | (g << (8 - sh))
            b[byte], b[byte + 1] = word >> 8, word & 0xFF
        i += length
    return bytes(b)


def steps_for(lufs, peak_db):
    """Gain steps that bring a track measured at `lufs` (sample peak `peak_db`) to TARGET_LUFS, a boost limited by the
    headroom."""
    steps = round((TARGET_LUFS - lufs) / STEP_DB)
    while steps > 0 and peak_db + steps * STEP_DB > HEADROOM_DB:
        steps -= 1
    return steps


def load_levels(sources_dir):
    """{source folder name: {track: steps}}, or {} when the package has no levels file."""
    p = os.path.join(sources_dir, LEVELS_FILE)
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
