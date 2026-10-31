"""Does the live knob land where the film's knob is?

The film's knob position is measured off the footage (tools/film_knob_frac.py),
and the player puts its knob so that the sprite's ink centroid rides that same
point.  This reads the knob's actual position out of the browser and compares the
two: on a dark, painted backdrop a pixel-space centroid of the whole band is
dominated by the artwork, so the browser's own geometry is the honest measure of
where the page drew it.

Geometry is not enough for the sprite itself: a knob whose mask image failed to
load still measures the right rect and still rides the bar, but paints as a
solid rectangle.  So the knob's own pixels are sampled too - the ink must cover
part of its rect, not all of it, and its corners must show the poster - and the
sprite's centroid must sit on the bar's centre row, not just at the right x.
"""
import io
import sys
sys.path.insert(0, "tools")
import json

import cv2
import numpy as np
from playwright.sync_api import sync_playwright
from build_art7 import BAR

FRACS = json.load(open("_frames/knob_frac.json"))
KNOB = json.load(open("_frames/knob_final.json"))
# the bar's own rows, measured once in build_art7 (it is the eraser's
# geometry too): one table, so a typo cannot make a check disagree with the build

TOL = 1.5          # px: the page puts the sprite's ink centroid on the film's
COVER_MIN, COVER_MAX = 0.10, 0.90   # of the knob's rect: sprite ink, not a block
bad = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1894})
    for s in range(1, 13):
        pg.goto(f"http://127.0.0.1:8770/index.html?t={s - 1}", wait_until="networkidle")
        pg.wait_for_function("window.__player")
        pg.evaluate("document.getElementById('phone').style.transform='scale(1)'")
        pg.evaluate("(f) => window.__player.preview(f)", FRACS[str(s)])
        got, state = pg.evaluate("""() => {
          const k = document.getElementById('knob');
          const r = k.getBoundingClientRect();
          const b = document.getElementById('bar').getBoundingClientRect();
          return [r.x + r.width / 2,
                  {top: r.top, h: r.height, w: r.width,
                   barTop: b.top, barH: b.height,
                   live: window.TRACKS[window.__player.index].live}];
        }""")
        bx0, _, bx1, _ = BAR[s]
        want = bx0 + FRACS[str(s)] * (bx1 - bx0)
        dx = got - want
        # the film's knob rides the bar's centre row; the sprite is positioned so
        # its own ink centroid lands there
        cy = KNOB[str(s)]["cy"]
        by = state["barTop"] + state["barH"] / 2
        dy = (state["top"] + cy) - by

        # the sprite's pixels: ink covers part of the rect and not its corners
        shot = pg.query_selector("#knob").screenshot()
        im = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)
        live = state["live"].lstrip("#")
        bgr = np.array([int(live[4:6], 16), int(live[2:4], 16), int(live[0:2], 16)],
                       np.int16)
        ink = (np.abs(im.astype(np.int16) - bgr).sum(2) < 90)
        cover = float(ink.mean())
        corners = [ink[1, 1], ink[1, -2], ink[-2, 1], ink[-2, -2]]
        mask_ok = COVER_MIN <= cover <= COVER_MAX and not any(corners)

        if abs(dx) > TOL:
            bad.append(s)
        if abs(dy) > TOL or not mask_ok:
            bad.append(s)
        print(f"{s:2d} page {got:6.1f}  film {want:6.1f}  dx={dx:+5.1f}  "
              f"dy={dy:+5.1f}  ink={cover:4.2f}"
              + ("   <-- CHECK" if (abs(dx) > TOL or abs(dy) > TOL or not mask_ok)
                 else ""))
    b.close()
print("FAILED:", ("song " + ", ".join(map(str, bad))) if bad else "none")
raise SystemExit(1 if bad else 0)
