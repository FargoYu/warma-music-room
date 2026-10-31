"""Does the picture actually play - and keep playing - in the browser?

Every other check photographs a paused page at a chosen moment.  A song is a
different situation: the clip runs while the audio does, and the failures the
player was built to avoid are visible only here - the drawing freezing while the
music goes on, dropping back to the still for a moment, or showing a frame that
is not the clip's.

Reading the video's clock around a screenshot is unreliable on the heavier
clips, so this does not trust any clock: it photographs the page a dozen times
while a song plays, matches every shot against the clip's own frames (at a
tenth of their size, which is enough to tell them apart), and asks whether that
frame index keeps moving.  A freeze is a run of identical indices; a hidden clip
is a run of index 0, which is the still; a stalled or backwards-playing clip is
a span that does not grow.

The live layer is masked out: the knob and the clock move on their own schedule
and are not what this measures.
"""
import json
import subprocess
import sys
import tempfile
import time

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, "tools")
import build_stills as bs

H = bs.ART_BOTTOM
GEOM = json.load(open("_frames/ui_geom.json"))
CL = json.load(open("_frames/clock_left_final.json"))
C = json.load(open("_frames/crops.json"))

SHOTS = 14          # photographs per song
RUN = 3             # identical indices in a row = the picture is not moving
SPAN = 8            # frames the picture must advance over the run
THUMB = (108, 160)  # w, h: enough to tell one frame from another
URL = "http://127.0.0.1:8770/index.html?t=%d"


def live_mask(s):
    """The page's own controls, which move on their own schedule."""
    m = np.ones((H, 1080), bool)
    x0, y0, x1, y1 = CL[str(s)]
    m[max(0, y0 - 18):min(H, y1 + 18), max(0, x0 - 18):min(1080, x1 + 18)] = False
    bx0, by0, bx1, by1 = bs.BAR[s]
    m[max(0, by0 - 30):min(H, by1 + 30), max(0, bx0 - 70):min(1080, bx1 + 70)] = False
    for k in ("prev", "next", "play"):
        q = GEOM[str(s)]["box"][k]
        m[max(0, q[1] - 10):min(H, q[3] + 10), max(0, q[0] - 10):min(1080, q[2] + 10)] = False
    return m


def thumbs(clip, td, n):
    """The clip's own frames at a tenth of their size."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", clip,
                    "-vf", f"scale={THUMB[0]}:{THUMB[1]},"
                           "scale=in_color_matrix=bt709:in_range=pc:out_range=pc",
                    "-pix_fmt", "bgr24", f"{td}/%04d.png"], check=True)
    out = []
    for k in range(1, n + 1):
        im = cv2.imread(f"{td}/{k:04d}.png")
        if im is None:
            raise RuntimeError(f"clip frame {k} did not decode")
        out.append(im.astype(np.int16))
    return out


def main():
    only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
    rows, bad = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": H})
        for s in only:
            keep = live_mask(s)
            clip = "web/" + C[str(s)]["src"].split("?")[0]
            try:
                with tempfile.TemporaryDirectory() as td:
                    refs = thumbs(clip, td, C[str(s)]["frames"])
                pg.goto(URL % (s - 1), wait_until="domcontentloaded")
                pg.wait_for_function("document.getElementById('pic0').complete")
                pg.evaluate("document.getElementById('phone').style.transform='scale(1)'")
                pg.evaluate("() => window.__player.play()")
                pg.wait_for_timeout(1200)          # the clip is fetched on first play
                small = cv2.resize(keep.astype(np.uint8), THUMB) > 0
                if not small.any():
                    raise RuntimeError("the live-layer mask is empty")
                idx = []
                for _ in range(SHOTS):
                    shot = pg.query_selector("#phone").screenshot()
                    im = cv2.imdecode(np.frombuffer(shot, np.uint8),
                                      cv2.IMREAD_COLOR)[:H, :1080]
                    th = cv2.resize(im, THUMB).astype(np.int16)
                    idx.append(int(min(range(len(refs)), key=lambda j: float(
                        np.abs(th - refs[j])[small].mean()))))
                    time.sleep(0.12)
            except Exception as e:
                bad.append(f"{s}: the page would not play ({type(e).__name__})")
                rows.append((s, 0, 0, 0.0))
                continue

            L = len(refs)
            # unwrap the loop: an index that jumps back by more than half the
            # clip is the clip starting again, not the picture running backwards
            unwrapped, total = [], 0
            for a, c in zip(idx, idx[1:]):
                d = c - a
                if d < -L // 2:
                    d += L
                elif d > L // 2:
                    d -= L
                total += d
                unwrapped.append(total)
            span = (max(unwrapped) - min(unwrapped)) if unwrapped else 0
            run, longest = 1, 1
            for a, c in zip(idx, idx[1:]):
                run = run + 1 if a == c else 1
                longest = max(longest, run)
            rows.append((s, len(idx), span, longest))
            if longest >= RUN:
                bad.append(f"{s}: the picture held one frame for {longest} shots")
            if span < SPAN:
                bad.append(f"{s}: the picture advanced {span} frames over the run")
        b.close()

    print(f"{'song':>4} {'shots':>6} {'frames':>7} {'held':>5}")
    for s, n, span, longest in rows:
        flag = "" if (longest < RUN and span >= SPAN) else "   <-- CHECK"
        print(f"{s:4d} {n:6d} {span:7.0f} {longest:5.0f}{flag}")
    print("FAILED:", "; ".join(bad) if bad else "none")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
