"""Erase what the player draws live: the scrub knob, the elapsed clock, the play
key and the heart.  Everything else - illustration, background, the six other
control icons, the bar line, the total-time clock - is left as the film drew it.

  * knob  - the film paints the knob once, but its measured centroid drifts a
            few pixels across a song, so its footprint is agreed on once for the
            whole song - widened by that measured travel - and the same
            silhouette is erased on every frame.  Rebuilding each erased row
            from that same row just outside the silhouette keeps the bar's
            antialiasing and follows the backdrop as it moves.
  * clock - the elapsed clock only.  Where it sits on a flat backdrop the box is
            repainted in that colour; where it sits on artwork its strokes are
            inpainted, leaving the illustration to carry on through.
  * glyph - the play key and the heart: solid painted shapes that the live layer
            redraws (the film has no pause state, and a like has to change the
            heart's fill).  Their ink is matched, the shape filled and grown, and
            the backdrop laid down or rebuilt as above.

Used by tools/build_stills.py, which writes both the still and the clip, so the
two always agree.
"""
import json

import cv2
import numpy as np

BAR = {1:(182,1355,897,1362), 2:(180,1357,899,1363), 3:(181,1356,899,1362),
       4:(180,1356,898,1362), 5:(182,1356,897,1362), 6:(181,1356,898,1362),
       7:(181,1356,901,1362), 8:(182,1356,900,1362), 9:(182,1355,900,1362),
       10:(180,1355,889,1362), 11:(182,1356,901,1362), 12:(184,1356,899,1362)}
INK = {1:(150,96,110),2:(74,55,57),3:(255,255,253),4:(135,101,100),5:(73,16,27),
       6:(255,253,255),7:(63,65,88),8:(150,97,105),9:(110,94,145),10:(26,1,82),
       11:(36,18,70),12:(103,41,64)}
# the heart's body colour, measured per song: the film draws the heart in two
# tones - a rim in the song's ink, a body in this - and the live layer needs both
# to find the whole glyph when the rim is thin or the body is far from the ink
HEART = {1:"#B5A1A1",2:"#D16E79",3:"#FFFFFF",4:"#8A6661",5:"#51121E",6:"#FFFFFF",
         7:"#3E435D",8:"#D84F53",9:"#C5E6EE",10:"#1F0955",11:"#22184D",12:"#6C2F42"}
BAND = 62
FLAT = 25.0   # ring spread, summed over three channels, that still counts as flat


def read(i):
    return cv2.imread(f"_frames/v/{i:04d}.jpg")


def local_bg(im, box, ink, ring=20):
    """The colour a control actually sits on, as BGR floats.

    The poster's flat base colour is the wrong reference wherever a drawing or a
    wave runs under a control: it reports about 1.5:1 for icons that sit on white
    at 13:1, and "fixing" those paints them out in a pale colour that is far
    harder to read than what the film drew.  So the backdrop is sampled from a
    ring just outside the box, skipping anything near the control ink.
    """
    x0, y0, x1, y1 = box
    ry0, ry1 = max(0, y0 - ring), min(im.shape[0], y1 + ring)
    rx0, rx1 = max(0, x0 - ring), min(im.shape[1], x1 + ring)
    patch = im[ry0:ry1, rx0:rx1]
    keep = np.ones(patch.shape[:2], bool)
    keep[max(0, y0 - ry0):y1 - ry0, max(0, x0 - rx0):x1 - rx0] = False   # the box itself
    f = patch.astype(np.float32)
    keep &= np.abs(f - np.array(ink, np.float32)).sum(axis=2) > 120
    f = f[keep]
    if len(f) < 40:
        return None
    return tuple(float(v) for v in np.median(f, axis=0))



# ---------------------------------------------------------------------------
# the scrub knob
# ---------------------------------------------------------------------------

def knob_band(s):
    """The band around the bar that holds the knob, in frame coordinates.

    Every consumer of the knob eraser needs exactly this box: the still, the
    clip and the checks measure the same silhouette only if they hand the same
    band to knob_silhouette().
    """
    bx0, by0, bx1, by1 = BAR[s]
    return (max(0, bx0 - 60), max(0, by0 - BAND),
            min(1080, bx1 + 60), min(1894, by1 + BAND))


def knob_candidates(im, s, pbox):
    """Every blob in the bar band that could be the knob.

    Inside the band the knob is the only thing taller than the bar line that also
    straddles it, but the artwork crossing the band can be taller still, so the
    caller must be able to see all candidates rather than one guess.
    """
    x0, y0, x1, y1 = pbox
    band = im[y0:y1, x0:x1]
    f = band.astype(np.float32)
    ink = np.array(INK[s][::-1], np.float32)
    d_ink = np.abs(f - ink).sum(axis=2)
    # local backdrop: a median wider than the knob, so the knob is not in it
    bg = cv2.medianBlur(cv2.copyMakeBorder(band, 30, 30, 30, 30, cv2.BORDER_REPLICATE),
                        61)[30:30 + band.shape[0], 30:30 + band.shape[1]].astype(np.float32)
    d_bg = np.abs(f - bg).sum(axis=2)
    m = (d_ink < d_bg) | (d_bg > 90)
    by0, by1 = BAR[s][1], BAR[s][3]
    thick = by1 - by0 + 1
    # a column run counts only if it is taller than the bar line
    tall = np.zeros(m.shape, np.uint8)
    for c in range(m.shape[1]):
        col = m[:, c]
        st = None
        for r in range(len(col) + 1):
            v = col[r] if r < len(col) else False
            if v and st is None:
                st = r
            elif not v and st is not None:
                if r - st > thick + 5:
                    tall[st:r, c] = 1
                st = None
    n, lab, stt, _ = cv2.connectedComponentsWithStats(tall, 8)
    cy = (by0 + by1) / 2 - y0
    out = []
    for k in range(1, n):
        x, y, w, h, area = stt[k]
        if area < 120 or w < 10 or h < 10 or w > 90 or h > 90:
            continue
        if not (y <= cy <= y + h):
            continue
        blob = (lab == k).astype(np.uint8)
        cnts, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(blob)
        cv2.drawContours(filled, cnts, -1, 1, -1)
        ys, xs = np.nonzero(filled)
        out.append({"mask": filled, "cx": float(xs.mean()), "cy": float(ys.mean()),
                    "area": int(area)})
    return out


_SIL_CACHE = {}


def knob_silhouette(s, a, b, pbox, samples=40):
    """The knob's footprint in the band, fixed for the whole song.

    Deciding the footprint per frame cannot work: the knob is painted once, so
    whichever blob wins on a given frame is a coin toss between the knob and
    whatever the drawing does behind it.  A frame where the
    drawing wins leaves the knob in the picture, a frame where the knob wins
    smears the drawing, and the clip plays the difference as a flicker.  So the
    masks are polled across the window, the place where candidates recur is taken
    as the knob, and every frame is erased with that one silhouette.
    """
    key = (s, a, b)
    if key in _SIL_CACHE:
        return _SIL_CACHE[key]
    step = max(1, (b - a) // samples)
    cands = []
    for i in range(a, b, step):
        cands.append(knob_candidates(read(i), s, pbox))
    flat = [(round(c["cx"] / 6.0), c) for cs in cands for c in cs]
    if not flat:
        _SIL_CACHE[key] = None
        return None
    # the recurring place: the 6 px bin that collects the most frames
    bins = {}
    for _, c in flat:
        bins.setdefault(round(c["cx"] / 6.0), set())
    votes = {k: set() for k in bins}
    for i, cs in enumerate(cands):
        for c in cs:
            votes[round(c["cx"] / 6.0)].add(i)
    anchor = max(votes, key=lambda k: (len(votes[k]), -abs(k)))
    here = [c for _, c in flat if round(c["cx"] / 6.0) == anchor]
    cx = float(np.median([c["cx"] for c in here]))
    keep = [c["mask"] for c in here if abs(c["cx"] - cx) <= 8]
    if not keep:
        _SIL_CACHE[key] = None
        return None
    # The knob is drawn at nearly the same place on every frame, but "nearly"
    # is up to 13 px of travel on some songs.  A majority vote leaves a crescent
    # of the knob on the frames where it sits at one end of that travel, and the
    # crescent rides the bar as the clip plays.  So the footprint is the common
    # mask widened by half the travel it was seen to make: the extremes of the
    # travel are where the knob is for a handful of frames, too few for a union
    # to keep them, but they are what the eye catches.
    acc = np.mean(np.stack(keep), axis=0)
    sil = (acc >= 0.5).astype(np.uint8)
    cxs = [c["cx"] for c in here if abs(c["cx"] - cx) <= 8]
    travel = (max(cxs) - min(cxs)) if cxs else 0.0
    half = int(round(travel / 2.0)) + 2
    if half > 1:
        sil = cv2.dilate(sil, np.ones((1, 2 * half + 1), np.uint8))
    # the knob wobbles a pixel or two as the drawing boils
    sil = cv2.dilate(sil, np.ones((5, 5), np.uint8))
    _SIL_CACHE[key] = sil
    return sil


def ring_backdrop(im, box, pad=7):
    """The backdrop just outside a box, and how flat it is.

    Sampled from below and from the sides, not from above: every control in the
    transport sits under the bar line, and a strip of the bar would report a
    backdrop that is not there.  Returns the median colour (BGR floats) and the
    85th percentile of how far the ring strays from it - a flat poster scores a
    few levels, a wash or linework scores tens, and a wave scores hundreds.
    """
    x0, y0, x1, y1 = box
    rx0, ry0 = max(0, x0 - pad), max(0, y0 - pad)
    rx1, ry1 = min(im.shape[1], x1 + pad), min(im.shape[0], y1 + pad)
    patch = im[ry0:ry1, rx0:rx1]
    keep = np.ones(patch.shape[:2], bool)
    keep[max(0, y0 - ry0):y1 - ry0, max(0, x0 - rx0):x1 - rx0] = False   # the box itself
    keep[:max(0, y0 - ry0), :] = False                                   # the bar above
    f = patch[keep].astype(np.float32)
    if len(f) < 40:
        return None, 999.0
    med = np.median(f, axis=0)
    return tuple(float(v) for v in med), float(np.percentile(np.abs(f - med).sum(axis=1), 85))


def rebuild(band, mask, axis="row", reach=26, clamp=None):
    """Rebuild the masked pixels from the picture just outside the mask.

    Each masked run is filled by blending the two ends of that same line of
    pixels, so whatever crosses the mask lengthwise carries straight through and
    the backdrop's own gradient survives.  An inpaint was the wrong tool: the
    place a control covers is never shown, so there is nothing to grow from, and
    it leaves a smooth smear on a flat poster and a dark blob where artwork runs
    under the shape.

    The axis matters.  Across the bar the backdrop varies sideways, so the lines
    to blend along are the rows; the elapsed clock sits under near-vertical
    linework on the posters that have any, so along the columns.  Filling along
    the wrong axis rubs the drawing out instead of carrying it through.
    `clamp(line_index)` may narrow the sample window where the samples have to
    come from a particular span of the picture.
    """
    out = band.copy()
    n = band.shape[1] if axis == "col" else band.shape[0]
    for i in range(n):
        line = band[:, i] if axis == "col" else band[i, :]
        cols = np.nonzero(mask[:, i] if axis == "col" else mask[i, :])[0]
        if not len(cols):
            continue
        a, b = int(cols[0]), int(cols[-1]) + 1
        lo, hi = clamp(i) if clamp else (0, len(line))
        l0, r1 = max(lo, a - reach), min(hi, b + reach)
        before = line[l0:a] if a > l0 else line[0:0]
        after = line[b:r1] if r1 > b else line[0:0]
        # an empty side is (1, 0, 3) - len() would call it non-empty, so test size
        has_b, has_a = before.size > 0, after.size > 0
        if not has_b and not has_a:
            continue
        med_b = np.median(before, axis=0) if has_b else np.median(after, axis=0)
        med_a = np.median(after, axis=0) if has_a else np.median(before, axis=0)
        t = np.linspace(0, 1, b - a)[:, None]
        fill = (med_b[None, :] * (1 - t) + med_a[None, :] * t).astype(np.uint8)
        if axis == "col":
            out[a:b, i] = fill
        else:
            out[i, a:b] = fill
    return out


def erase_knob(im, s, sil, pbox):
    """Remove the knob by rebuilding its silhouette from the row it sits in.

    The knob never leaves its stretch of the bar, so no frame of the segment
    shows what is underneath it: a median plate there is a median of knob pixels,
    and inpainting has nothing clean to grow from.  The band is horizontally
    uniform there - a bar line over a backdrop - so each row is rebuilt from that
    same row just outside the silhouette.  Because the silhouette is the same on
    every frame the patch never appears or vanishes as the clip plays.
    """
    if sil is None:
        return im
    x0, y0, x1, y1 = pbox
    bx0, by0, bx1, by1 = BAR[s]
    la, lb = bx0 - x0, bx1 - x0          # the bar's own span, in band coordinates

    def clamp(r):
        # On a bar row the samples must come from the bar itself: where the knob
        # sits at the bar's start, the pixels to its left are bare background, and
        # blending them in would paint a gradient stub onto the bar.
        return (la, lb) if (by0 - y0) <= r <= (by1 - y0) else (0, im.shape[1])

    im = im.copy()
    im[y0:y1, x0:x1] = rebuild(im[y0:y1, x0:x1], sil, "row", clamp=clamp)
    return im


def erase_glyph(im, box, ink_rgb, tol=120.0, pad=22):
    """Remove a painted control glyph: the play key, the heart.

    Both are drawn live by the player - the key because the film never shows a
    pause state, the heart because a like has to change its fill - so the film's
    own drawing of them has to go.  It is a solid shape covering whatever the
    poster has behind it.  On a flat backdrop the ring around the box says what colour to
    lay down, and laying it down exactly is the only fill that leaves nothing
    behind - the stroke's soft outer rim survives any pass that only looks for
    ink, and reads as a ghost of the glyph.  Elsewhere the rows are rebuilt from
    their own edges, the same way the knob's are; an inpaint there fills the shape
    with a dark blob, and the patch is grown first so those edges are real picture
    rather than the glyph's own rim.
    """
    x0, y0, x1, y1 = box
    px0, py0 = max(0, x0 - pad), max(0, y0 - pad)
    px1, py1 = min(im.shape[1], x1 + pad), min(im.shape[0], y1 + pad)
    band = im[py0:py1, px0:px1]
    f = band.astype(np.float32)
    # one ink, or every ink the glyph is drawn in (the heart's rim and its body):
    # matching only the rim works while the rim is thick, and silently finds
    # almost nothing - the eraser then returns the image untouched - where it is
    # thin or the body colour is far from it
    inks = ink_rgb if (len(ink_rgb) and isinstance(ink_rgb[0], (list, tuple, np.ndarray))) else [ink_rgb]
    m = np.zeros(f.shape[:2], np.uint8)
    for c in inks:
        m |= (np.abs(f - np.array(c, np.float32)).sum(axis=2) < tol).astype(np.uint8)
    inner = np.zeros(m.shape, np.uint8)
    inner[y0 - py0:y1 - py0, x0 - px0:x1 - px0] = 1
    m &= inner
    if m.sum() < 40:
        return im
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n < 2:
        return im
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    m = (lab == k).astype(np.uint8)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    m = np.zeros_like(m)
    cv2.drawContours(m, cnts, -1, 1, -1)          # fill holes inside the glyph
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))  # its antialiased rim
    col, flat = ring_backdrop(im, box)
    if col is not None and flat < FLAT:
        # the film draws the key with a soft halo, which is neither ink nor
        # backdrop; on a flat backdrop anything near the shape that is still off
        # that colour is the halo
        off = np.abs(f - np.array(col, np.float32)).sum(axis=2) > 18
        near = cv2.dilate(m, np.ones((15, 15), np.uint8)) > 0
        band[(off & near) | (m > 0)] = np.array(col, np.uint8)
    else:
        band[:] = rebuild(band, m, "row", reach=pad)
    out = im.copy()
    out[py0:py1, px0:px1] = band
    return out



def erase_clock(im, box, ink_rgb, pad=16):
    """Remove the elapsed clock's handwriting.

    Two cases, decided from the ring outside the box: on a flat backdrop the box
    is painted in that colour, which is the only fill that leaves nothing of the
    handwriting behind - a fill that looks for ink leaves the stroke's soft outer
    rim, and that rim reads as a ghost of the digits.  On artwork the strokes are
    masked and the picture is rebuilt through them along the columns, because the
    drawings that carry linework behind the clock draw it near-vertically and a
    row-wise fill would rub those lines out.

    The flat test is measured on the ring, not inside the box: the handwriting
    and its rim occupy enough of the box to make a textured poster look flat and
    a flat poster look textured.
    """
    col, flat = ring_backdrop(im, box)
    if col is not None and flat < FLAT:
        x0, y0, x1, y1 = box
        im[y0:y1, x0:x1] = np.array(col, np.uint8)
        return im
    return _scrub(im, box, ink_rgb, pad, rounds=1)


def scrub_clock(im, box, ink_rgb, rounds=3):
    """Repeat the clock removal until nothing of the handwriting is left.

    One pass of masking leaves the faintest antialiased rim behind, and that rim
    reads as a grey smudge.  Each extra pass re-measures the backdrop from the
    now-cleaner box and takes out whatever is still off it.

    Only pixels nearer the ink than the backdrop may go: a pass that masks
    anything off its local median would erase the artwork's own texture instead,
    which is how a clock-sized blur gets left on a busy poster.
    """
    return _scrub(im, box, ink_rgb, 16, rounds)


def _scrub(im, box, ink_rgb, pad, rounds):
    """Mask the handwriting in the box and rebuild the picture through it.

    The patch is grown by `pad` so each masked run has real picture to blend from
    on both sides; only pixels inside the box are ever rewritten.  The last pass
    takes the stroke's soft outer rim, which is neither near the ink nor off the
    backdrop by enough to be caught before, and is what a half-erased clock
    leaves behind: a ghost of the digits.  It may only look one to two pixels
    from where the ink was, or it would take the drawing with it.
    """
    x0, y0, x1, y1 = box
    gx0, gy0 = max(0, x0 - pad), max(0, y0 - pad)
    gx1, gy1 = min(im.shape[1], x1 + pad), min(im.shape[0], y1 + pad)
    ink = np.array(ink_rgb, np.float32)
    inner = np.zeros((gy1 - gy0, gx1 - gx0), np.uint8)
    inner[y0 - gy0:y1 - gy0, x0 - gx0:x1 - gx0] = 1
    done = np.zeros(inner.shape, np.uint8)
    for n in range(rounds + 1):
        roi = im[gy0:gy1, gx0:gx1]
        f = roi.astype(np.float32)
        bg = cv2.medianBlur(roi, 21).astype(np.float32)
        d_bg = np.abs(f - bg).sum(axis=2)
        if n < rounds:
            d_ink = np.abs(f - ink).sum(axis=2)
            m = ((d_ink < d_bg) & (d_bg > 20)).astype(np.uint8)
        else:
            # the rim, only where it touches what was already taken
            m = (cv2.dilate(done, np.ones((7, 7), np.uint8)) & (d_bg > 12)).astype(np.uint8)
            m &= 1 - done
        m &= inner
        if m.sum() < 6:
            break
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        m = cv2.dilate(m, np.ones((5, 5), np.uint8))
        m &= inner
        roi[:] = rebuild(roi, m, "col", reach=pad)
        done |= m
    return im




