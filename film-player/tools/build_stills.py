"""Cut the artwork out of the footage: one lossless still per song.

The still is the frame the clip starts on, prepared by prepare(): the film's own
chroma rebuilt where 4:2:0 subsampling left block structure (dechroma), and the
four things the player draws live - the scrub knob, the elapsed clock, the play
key and the heart - erased with tools/build_art7.py's erasers.  The transport
row keeps the film's own shapes and its ink; only ink that has effectively
vanished (under 2:1 on the backdrop behind its box) is moved, per box (recolor).

tools/build_anim.py runs the same prepare() on every frame of the song's loop
window, so the still and the clip agree pixel for pixel at frame zero.
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import build_art7 as ba          # the erasers: erase_knob, erase_clock, scrub_clock
from build_art7 import BAR

W = json.load(open("_frames/art_windows.json"))
CL = json.load(open("_frames/clock_left_final.json"))
CLOCK_INK = json.load(open("_frames/clock_ink.json"))
# the bar's own rows, measured once in build_art7 (it is the eraser's
# geometry too): one table, so a typo cannot make a check disagree with the build
OUT = "web/assets/pic"
# the artwork ends here: below the transport row there is only background and
# the uploader's watermark, so the bottom strip is cropped away outright
ART_BOTTOM = 1600
GEOM = json.load(open("_frames/ui_geom.json"))
TRANSPORT = ("prev", "next")


def _lum(h):
    # callers hand in BGR (cv2's order), so the first channel is blue
    b, g, r = [v / 255 for v in h]
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def readable(ink, bg, target):
    """The song's ink, pushed along its own grey axis until it is legible."""
    def cr(a, b):
        la, lb = _lum(a), _lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
    if cr(ink, bg) >= target:
        return ink
    toward = 0.0 if _lum(bg) > 0.18 else 255.0
    for step in range(1, 101):
        f = step / 100.0
        c = tuple(v + (toward - v) * f for v in ink)
        if cr(c, bg) >= target:
            return c
    return tuple([toward] * 3)


def recolor(im, boxes, ink, base, tol=45.0, ratio=2.0, skip=()):
    """Move pixels that are the control ink toward ink that is legible on them.

    The weight is soft, so the antialiased rim of a glyph is carried along
    instead of being left as a pale halo.  Each box is measured against the
    backdrop that is actually behind it, not the poster's flat base colour: a
    control sitting on the drawing needs a different ink from one sitting on the
    poster, and using one colour for both either leaves a control unreadable or
    repaints it for no reason.

    The floor is 2:1, deliberately low: this is a safety net for ink that has all
    but vanished (the 1.5:1 posters), not a restyling.  A control that straddles
    two tones - song 10's prev/next sit half on a white cloud, half on violet -
    has no single corrected colour that reads on both, and lifting the film's
    dark ink there only makes it disappear on the white.  At 3:1 that is exactly
    what happened.  Boxes listed in `skip` are left alone entirely:
    they hold what the erasers rebuilt, and pushing a rebuilt patch toward a new
    colour paints a solid block where the artwork used to be.
    """
    ink = np.array(ink, np.float32)

    def cr(a, b):
        la, lb = _lum(a), _lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    plans = []
    for box in boxes:
        # one region, or a list of regions that are one control drawn twice
        # (prev/next): those get a single colour, chosen for their worst
        # backdrop - measured per box the pair would come out in two colours
        group = box if isinstance(box[0], (list, tuple)) else [box]
        bgs = [g for g in (ba.local_bg(im, b, ink) for b in group) if g is not None]
        bg = min(bgs, key=lambda c: cr(ink, c)) if bgs else base
        tgt = np.array(readable(tuple(ink), bg, ratio), np.float32)
        for b in group:
            plans.append((b, tgt))
    for (x0, y0, x1, y1), tgt in plans:
        roi = im[y0:y1, x0:x1]
        f = roi.astype(np.float32)
        d = np.sqrt(((f - ink) ** 2).sum(axis=2))
        w = np.clip(1.0 - d / tol, 0.0, 1.0)
        for (sx0, sy0, sx1, sy1) in skip:
            w[max(0, sy0 - y0):max(0, sy1 - y0), max(0, sx0 - x0):max(0, sx1 - x0)] = 0.0
        w = w[..., None]
        roi[:] = np.clip(f * (1 - w) + tgt * w, 0, 255).astype(np.uint8)
    return im
N = 1                     # one still per song; the motion comes from the clip
# background colours as BGR (cv2's order), matching ba.INK's reversal
BG = {1:(255,255,255),2:(220,189,85),3:(82,81,252),4:(234,244,248),5:(233,240,248),
      6:(142,77,84),7:(41,31,34),8:(245,252,251),9:(207,204,209),10:(135,41,52),
      11:(154,110,251),12:(244,250,254)}


# ---------------------------------------------------------------------------
# one frame of the artwork, ready to be shown: the source frame with the
# uploader's video chroma rebuilt, and everything the player animates removed.
# Used by both the still and the moving clip, so the two agree exactly.
# ---------------------------------------------------------------------------

def dechroma(im, strength=1.0):
    """Rebuild the chroma the source video lost to 4:2:0 subsampling.

    Bilibili encodes in yuv420p, so the film's flat areas carry a faint
    8x8 block structure - visible as thin stripes when the artwork is scaled
    up.  Luma keeps its edges (the drawing is luma), so the chroma is smoothed
    only where the luma is flat: block noise goes, colour edges stay.
    """
    ycrcb = cv2.cvtColor(im, cv2.COLOR_BGR2YCrCb)
    y = ycrcb[:, :, 0].astype(np.float32)
    edge = np.abs(cv2.Laplacian(y.astype(np.uint8), cv2.CV_32F))
    # smooth where the luma is flat, keep the chroma edge where the luma has one
    k = (1.0 - np.clip(edge / 24.0, 0.0, 1.0))[..., None] * strength
    for ch in (1, 2):
        c = ycrcb[:, :, ch].astype(np.float32)
        blur = cv2.blur(c, (9, 9))
        ycrcb[:, :, ch] = np.clip(c * (1 - k[:, :, 0]) + blur * k[:, :, 0], 0, 255).astype(np.uint8)
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)


def prepare(s, f, sil, pbox):
    """The film's frame with everything the player animates taken out."""
    im = ba.read(f)
    im = dechroma(im)
    im = ba.erase_knob(im, s, sil, pbox)
    raw = CL[str(s)]
    ink = np.array(ba.INK[s][::-1], np.float32)
    # the handwriting was measured on its own: on a poster where the clock sits
    # on bright artwork its strokes are lighter than the transport row's ink, and
    # masking in the transport ink loses them on exactly those frames
    hand = np.array([int(CLOCK_INK[str(s)][5:7], 16), int(CLOCK_INK[str(s)][3:5], 16),
                     int(CLOCK_INK[str(s)][1:3], 16)], np.float32)
    box = [max(0, raw[0] - 4), max(0, raw[1] - 4),
           min(1080, raw[2] + 4), min(1894, raw[3] + 4)]
    im = ba.erase_clock(im, box, hand)
    im = ba.scrub_clock(im, box, hand)
    # The play key and the heart are drawn live - the film never shows a pause
    # state, and a like has to change the heart's fill - so the film's own
    # drawing of them is erased here.  The other six icons stay painted: nothing
    # about them changes, so the film's own ink is the best copy there is.
    pb = GEOM[str(s)]["box"]["play"]
    im = ba.erase_glyph(im, (pb[0] - 3, pb[1] - 3, pb[2] + 3, pb[3] + 3), ink)
    hb = GEOM[str(s)]["box"]["heart"]
    # the heart is two-tone: a rim in the song's ink and a body in the heart
    # colour. Both are handed to the eraser, so a thin rim cannot leave the
    # body behind and a body far from the ink cannot take the rim with it.
    hc = ba.HEART[s]
    hink = np.array([int(hc[5:7], 16), int(hc[3:5], 16), int(hc[1:3], 16)], np.float32)
    im = ba.erase_glyph(im, (hb[0] - 3, hb[1] - 3, hb[2] + 3, hb[3] + 3), [ink, hink])
    # the transport group keeps the film's own shapes; only its colour is moved
    # toward the readable ink where the poster's ink is nearly invisible
    # the transport row keeps the film's shapes; only its ink is moved, and only
    # inside those boxes, so the drawing behind is left alone
    bx0, by0, bx1, by1 = BAR[s]
    # the bar's box is the bar's own rows, not a band around them: grown any
    # further, the box catches the artwork the bar crosses - and on a poster whose
    # drawing is the same ink as its controls, that paints a block of the drawing
    # over in the readable colour
    boxes = [(bx0 - 2, by0 - 1, bx1 + 2, by1 + 1),
             (max(0, bx1 - 110), by1 + 3, min(1080, bx1 + 12), by1 + 48)]
    pair = []
    for name in TRANSPORT:
        q = GEOM[str(s)]["box"][name]
        pair.append((q[0] - 4, q[1] - 4, q[2] + 4, q[3] + 4))
    boxes.append(pair)      # prev and next are one control, so one ink
    rebuilt = [tuple(box), (pb[0] - 3, pb[1] - 3, pb[2] + 3, pb[3] + 3),
               (hb[0] - 3, hb[1] - 3, hb[2] + 3, hb[3] + 3)]
    return recolor(im, boxes, ink, BG[s], tol=45.0, ratio=2.0, skip=rebuilt)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
    # merge: a one-song rebuild must not drop the other songs' entries
    meta = json.load(open("_frames/stills.json"))         if os.path.exists("_frames/stills.json") else {}
    # record the window each song was cut from, next to what is already there
    built = json.load(open("_frames/art_windows.json"))         if os.path.exists("_frames/art_windows.json") else {}
    for s in only:
        a, L = W[str(s)]["start"], W[str(s)]["length"]
        pbox = ba.knob_band(s)
        # the knob's footprint, agreed once for the song: see ba.knob_silhouette
        sil = ba.knob_silhouette(s, a, a + L, pbox)
        # one still, the clip's own first frame: every pose and every boil is
        # the clip's business, the still only has to be the paused picture
        picks = [a + i * L // N for i in range(N)]
        files = []
        for k, f in enumerate(picks):
            im = prepare(s, f, sil, pbox)[:ART_BOTTOM]
            out = f"{OUT}/{s:02d}_{k}.png"
            cv2.imwrite(out, im, [cv2.IMWRITE_PNG_COMPRESSION, 6])
            files.append(f"assets/pic/{s:02d}_{k}.png")
            print(f"{s:2d} frame {f}  {os.path.getsize(out)/1e3:5.0f} kB", flush=True)
        meta[str(s)] = {"frames": picks, "pics": files}
        built[str(s)] = {"start": a, "length": L}
    for path, obj in (("_frames/stills.json", meta),
                      ("_frames/art_windows.json", built)):
        tmpf = path + ".tmp"
        json.dump(obj, open(tmpf, "w"), indent=1)
        os.replace(tmpf, path)
    print("wrote _frames/stills.json")
