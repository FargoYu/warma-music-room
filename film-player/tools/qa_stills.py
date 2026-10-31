"""QA for the stills build: erasure, page fidelity, and that the clip moves.

Three questions, per song:
  still vs film   - the cut drawing is the film's frame minus only the knob, the
                    elapsed clock, the play key and the contrast-corrected
                    transport ink, so anything else that differs by more than
                    codec noise is a stroke left behind.
  page vs still   - the page's own rendering of the same drawing (paused, so the
                    clip is held off) must reproduce it pixel for pixel outside
                    the elements the live layer draws.
  glyph erased    - the play key and the heart are drawn live, so their boxes are
                    excluded from the two comparisons above; this asks the erased
                    boxes directly, where an eraser that never ran leaves the
                    film's painted glyph exactly as drawn.
  clip moves      - the clip's frames must actually differ, or the motion is a
                    still picture being played.
  still is frame 0 - the page shows the still until the clip has been fetched,
                    so the still has to be the clip's own first frame: any gap
                    between them is a jump at the moment playback starts.
"""
import json
import sys

import subprocess
import tempfile

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, "tools")
import build_art7 as ba          # the knob's own silhouette, so the mask matches
from build_art7 import BAR
import build_stills as bs        # for ART_BOTTOM, not for its side effects

S = json.load(open("_frames/stills.json"))
AW = json.load(open("_frames/art_windows.json"))
CROPS = json.load(open("_frames/crops.json"))
H = bs.ART_BOTTOM   # the artwork is cropped below the transport row
GEOM = json.load(open("_frames/ui_geom.json"))
CL = json.load(open("_frames/clock_left_final.json"))
# the bar's own rows, measured once in build_art7 (it is the eraser's
# geometry too): one table, so a typo cannot make a check disagree with the build
RESIDUE = 60      # per-pixel difference that is a stroke, not codec noise
MOTION = 0.05     # mean difference the clip must show between two moments
GLYPH_RESIDUAL = 0.10  # of the film's ink in those boxes, the share that may
                       # still match it: a mean alone can pass a half-removed
                       # glyph, because the half that did change scores high
GLYPH_ERASED = 12.0  # mean difference the still must show over the film's ink in
                     # the play/heart boxes.  The live layer draws there, so an
                     # eraser that never ran is otherwise invisible to QA.  The
                     # scale is measured: with the erasers disabled the still
                     # differs only by dechroma, 1.5-2.6; enabled builds measure
                     # 29-128, the low being the posters whose own glyph ink is
                     # within ~30 levels of the backdrop (song 7) - a per-pixel
                     # "is it gone" threshold would call that erase a no-op.


def knob_box(s):
    """Where the film's own knob sits: it overhangs the bar on both sides."""
    a, L = AW[str(s)]["start"], AW[str(s)]["length"]
    pbox = ba.knob_band(s)
    sil = ba.knob_silhouette(s, a, a + L, pbox)
    if sil is None:
        return None
    ys, xs = np.nonzero(sil)
    return (int(xs.min()) + pbox[0] - 4, int(ys.min()) + pbox[1] - 4,
            int(xs.max()) + pbox[0] + 4, int(ys.max()) + pbox[1] + 4)


def clip_frame0(src):
    """The clip's first frame through the conversion the page uses.

    No frame selector: ffmpeg's first output frame is frame 0, and the select
    filter needs a backslash escaped through two parsers for no gain here.
    """
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                        "-vf", "scale=in_color_matrix=bt709:in_range=pc:out_range=pc",
                        "-frames:v", "1", "-pix_fmt", "bgr24", f"{td}/f0.png"],
                       check=True)
        return cv2.imread(f"{td}/f0.png")


def glyph_gone(s, still, film):
    """How much of the film's painted play key and heart the still removed.

    The boxes are excluded from both comparisons above (the live layer covers
    them), so nothing else asks these two questions - and a box that still
    matches the film exactly is a glyph the eraser never erased, which shows
    through the live one as a doubling.

    The ink is the film's own: pixels that differ from the box's surrounding
    ring, which works on a busy poster as well as a flat one.

    Two numbers are returned because one is not enough: the mean difference
    rises with the *share* of ink removed, so a half-erased glyph with a strong
    remnant still scores well - the share of ink that still matches the film
    within `RESIDUE` is what says the glyph is gone.  A disabled eraser reads
    mean 1.5-2.6; the enabled builds read 29-209 with a residual share of 0.
    """
    def bgr(hex_):
        return np.array([int(hex_[5:7], 16), int(hex_[3:5], 16),
                         int(hex_[1:3], 16)], np.float32)

    worst = (float("inf"), 0.0)   # no film ink in either box: nothing to erase
    for key in ("play", "heart"):
        x0, y0, x1, y1 = GEOM[str(s)]["box"][key]
        roi = film[y0:y1, x0:x1].astype(np.float32)
        ring = np.concatenate([roi[0], roi[-1], roi[:, 0], roi[:, -1]])
        ink = np.abs(roi - np.median(ring, axis=0)).sum(2) > RESIDUE
        if not ink.any():
            continue
        d = np.abs(still[y0:y1, x0:x1].astype(np.int16)
                   - film[y0:y1, x0:x1].astype(np.int16)).max(2)
        # the glyph is what the eraser was aimed at: strokes in one of the inks
        # the film drew it in.  A stroke of someone else's artwork that happens
        # to cross the box is not the eraser's to remove, and counting it as
        # residue reads song 10's play box (a dark line under a dark triangle)
        # as 27% unerased.
        inks = [np.array(ba.INK[s][::-1], np.float32)]
        if key == "heart":
            inks.append(bgr(ba.HEART[s]))
        near = np.zeros(ink.shape, bool)
        for c in inks:
            near |= np.abs(roi - c).sum(2) < 120
        glyph = near & ink
        if not glyph.any():
            glyph = ink
        # 16 levels: a disabled eraser differs only by dechroma (1.5-2.6), while
        # the weakest real erase (song 7, ink only ~30 from its backdrop) moves
        # every glyph pixel by more than that
        worst = (min(worst[0], float(d[glyph].mean())),
                 max(worst[1], float((d[glyph] <= 16).mean())))
    return worst


def rebuilt(s):
    """The places the still is meant to differ from the film."""
    m = np.ones((H, 1080), bool)
    x0, y0, x1, y1 = CL[str(s)]
    m[max(0, y0 - 18):min(H, y1 + 18), max(0, x0 - 18):min(1080, x1 + 18)] = False
    bx0, by0, bx1, by1 = BAR[s]
    m[max(0, by0 - 10):min(H, by1 + 10), max(0, bx0 - 4):min(1080, bx1 + 4)] = False
    m[by1:min(H, by1 + 50), max(0, bx1 - 115):min(1080, bx1 + 15)] = False   # total time
    k = knob_box(s)
    if k:
        m[max(0, k[1]):min(H, k[3]), max(0, k[0]):min(1080, k[2])] = False
    for key in ("prev", "next", "play", "heart"):
        q = GEOM[str(s)]["box"][key]
        m[max(0, q[1] - 10):min(H, q[3] + 10), max(0, q[0] - 10):min(1080, q[2] + 10)] = False
    return m


def main():
    only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
    rows = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": H})
        for s in only:
            st = [cv2.imread("web/" + p) for p in S[str(s)]["pics"]]
            film = cv2.imread(f"_frames/v/{S[str(s)]['frames'][0]:04d}.jpg")[:H]
            d_film = np.abs(st[0].astype(np.int16) - film.astype(np.int16)).max(2)
            keep = rebuilt(s)
            residue = int((d_film * keep > RESIDUE).sum())
            gone, resid = glyph_gone(s, st[0], film)

            # the clip must carry motion: compare its first and middle frame
            cap = cv2.VideoCapture("web/" + CROPS[str(s)]["src"].split("?")[0])
            ok0, f0 = cap.read()
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
            ok1, f1 = cap.read()
            cap.release()
            motion = (float(np.abs(f1.astype(np.int16) - f0.astype(np.int16)).mean())
                      if (ok0 and ok1 and f0 is not None and f1 is not None) else 0.0)

            c0 = clip_frame0("web/" + CROPS[str(s)]["src"].split("?")[0])
            d0 = int(np.abs(c0[:H].astype(np.int16)
                            - st[0].astype(np.int16)).max(2).max()) if c0 is not None else 999

            pg.goto(f"http://127.0.0.1:8770/index.html?t={s - 1}", wait_until="networkidle")
            pg.wait_for_function("document.getElementById('pic0').complete")
            pg.evaluate("document.getElementById('phone').style.transform='scale(1)'")
            # where the page drew the live knob: it is the page's, not the still's
            kb = pg.evaluate('''() => {
              const p = document.getElementById('phone').getBoundingClientRect();
              const k = document.getElementById('knob').getBoundingClientRect();
              return [k.left - p.left, k.top - p.top, k.right - p.left, k.bottom - p.top];
            }''')
            # element screenshot: the phone is scaled and centred by CSS
            pg.query_selector("#phone").screenshot(path=f"_frames/live/{s:02d}.png")
            live = cv2.imread(f"_frames/live/{s:02d}.png")[:H, :1080]

            # the live layer draws these, so they are not the page's to reproduce
            m = keep.copy()
            q = GEOM[str(s)]["box"]["play"]
            m[max(0, q[1] - 10):min(H, q[3] + 10), max(0, q[0] - 10):min(1080, q[2] + 10)] = False
            m[max(0, int(kb[1]) - 6):min(H, int(kb[3]) + 6),
              max(0, int(kb[0]) - 6):min(1080, int(kb[2]) + 6)] = False
            d_page = np.abs(live.astype(np.int16) - st[0].astype(np.int16)).max(2)
            rows.append((s, float(d_film.mean()), residue, gone, resid, d0,
                         float(d_page[m].mean()),
                         int((d_page * m > RESIDUE).sum()), motion))
        b.close()

    bad = []
    print(f"{'song':>4} {'still/film':>11} {'residue':>8} {'glyph':>6} {'left':>6} "
          f"{'frame0':>7} {'page/still':>11} {'page px':>8} {'motion':>7}")
    for s, df, residue, gone, resid, d0, dp, pagepx, motion in rows:
        ok = (residue == 0 and gone >= GLYPH_ERASED and resid <= GLYPH_RESIDUAL
              and d0 <= 16 and pagepx == 0 and motion > MOTION)
        flag = "" if ok else "   <-- CHECK"
        if residue:
            bad.append(f"{s}: {residue} px of the film's own ink left in the still")
        if gone < GLYPH_ERASED:
            bad.append(f"{s}: the play key/heart is still painted in the still "
                       f"(the film's ink still matches within {gone:.1f} levels, "
                       f"floor {GLYPH_ERASED:.0f})")
        if d0 > 16:
            bad.append(f"{s}: the still is not the clip's first frame "
                       f"(worst channel differs by {d0})")
        if resid > GLYPH_RESIDUAL:
            bad.append(f"{s}: {resid:.0%} of the play key/heart ink still matches "
                       f"the film (ceiling {GLYPH_RESIDUAL:.0%})")
        if pagepx:
            bad.append(f"{s}: {pagepx} px where the page does not reproduce the still")
        if motion <= MOTION:
            bad.append(f"{s}: the clip does not move ({motion:.2f})")
        print(f"{s:4d} {df:11.2f} {residue:8d} {gone:6.2f} {resid:6.2f} "
              f"{d0:7d} {dp:11.2f} {pagepx:8d} {motion:7.2f}{flag}")
    print("FAILED:", "; ".join(bad) if bad else "none")
    sys.exit(1 if bad else 0)



if __name__ == "__main__":
    sys.exit(main())
