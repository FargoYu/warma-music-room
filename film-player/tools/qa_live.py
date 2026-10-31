"""QA for the art layer, frame by frame.

qa_stills compares the page with the still it starts from - one moment per song.
The clip plays the film's own frames over that still, so the per-frame question
is different: does the page, on frame k, show what frame k of the clip actually
is?  A clip that is scaled, letterboxed, colour-converted with the wrong matrix
or shifted by a pixel reproduces frame 0 well enough to pass a single-moment
check and drifts away from the rest.

The live layer is hidden for the comparison: this check is about the art layer
only, and the live controls have their own checks (knob_check, clock_check) and
their own page-fidelity check in qa_stills.

A seek is only a request: the browser shows what it has decoded when it has
decoded it.  So each shot is checked for *which* frame it shows, by content, and
re-shot until it is the frame asked for - a shot taken while the previous frame
is still up is not a page defect, and a page that cannot reach the frame is.

Sampled frames per song: first, two interior thirds, last.  Each is asked for at
the *middle* of its own interval: a seek to a frame's boundary is a coin toss
between it and its neighbour, because the browser floors a presentation time and
the film's drawings differ from frame to frame by far more than codec noise.
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

W = json.load(open("_frames/art_windows.json"))
C = json.load(open("_frames/crops.json"))
H = bs.ART_BOTTOM   # the artwork is cropped below the transport row
FPS = 30
TOL = 60            # per-pixel difference that is a real mismatch, not codec noise
PAGE_MAX = 40       # pixels over TOL the page may differ by on a whole frame
TRIES = 6           # shots the page gets to show the frame it was asked for
WAIT = 0.4          # seconds between them

URL = "http://127.0.0.1:8770/index.html?t=%d"

SHOW = """(src) => {
  const v = document.getElementById('crop');
  document.getElementById('ui').style.display = 'none';
  v.hidden = false;
  v.preload = 'auto';
  if (v.getAttribute('src') !== src) { v.src = src; v.load(); }
}"""


def frames(s):
    L = W[str(s)]["length"]
    return [0, L // 3, 2 * L // 3, L - 1]


def decode(clip, ks, td):
    """The clip's own frames, through the same BT.709 conversion the page uses."""
    sel = "+".join("eq(n\\,%d)" % k for k in ks)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", clip,
                    "-vf", f"select='{sel}',"
                           "scale=in_color_matrix=bt709:in_range=pc:out_range=pc",
                    "-fps_mode", "passthrough", "-pix_fmt", "bgr24",
                    f"{td}/%04d.png"], check=True)
    return [cv2.imread(f"{td}/{i + 1:04d}.png") for i in range(len(ks))]


def main():
    only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
    rows, bad = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": H})
        for s in only:
            ks = frames(s)
            clip = "web/" + C[str(s)]["src"].split("?")[0]
            worst, px, misses = 0.0, 0, 0
            try:
                with tempfile.TemporaryDirectory() as td:
                    want = decode(clip, ks, td)
                pg.goto(URL % (s - 1), wait_until="domcontentloaded")
                pg.wait_for_function("document.getElementById('pic0').complete")
                pg.evaluate("document.getElementById('phone').style.transform='scale(1)'")
                src = pg.evaluate("window.TRACKS[window.__player.index].crop.src")
                pg.evaluate(SHOW, src)
                pg.evaluate("""() => new Promise(r => {
                  const v = document.getElementById('crop');
                  v.readyState >= 1 ? r() : v.addEventListener('loadedmetadata', r, {once: true});
                })""")
                for i, k in enumerate(ks):
                    pg.evaluate("""(t) => {
                      const v = document.getElementById('crop');
                      v.pause(); v.currentTime = t;
                    }""", (k + 0.5) / FPS)
                    page = None
                    for try_no in range(TRIES):
                        time.sleep(WAIT)
                        shot = pg.query_selector("#phone").screenshot()
                        page = cv2.imdecode(np.frombuffer(shot, np.uint8),
                                            cv2.IMREAD_COLOR)[:H, :1080]
                        # which of the sampled frames is this shot?  A small
                        # thumbnail is enough to tell them apart, and it keeps
                        # this cheap
                        got = min(range(len(ks)), key=lambda j: np.abs(
                            cv2.resize(page, (32, 16)).astype(np.int16)
                            - cv2.resize(want[j], (32, 16)).astype(np.int16)).mean())
                        if got == i:
                            break
                    if page is None or got != i:
                        misses += 1
                        continue
                    ref = want[i]
                    d = np.abs(page.astype(np.int16) - ref.astype(np.int16)).max(2)
                    worst = max(worst, float(d.mean()))
                    px += int((d > TOL).sum())
            except Exception as e:                       # a hang is a failure too
                bad.append(f"{s}: the page would not show the clip ({type(e).__name__})")
            rows.append((s, len(ks), worst, px, misses))
            if px > PAGE_MAX:
                bad.append(f"{s}: {px} px where the page is not the clip's own frame")
            if misses:
                bad.append(f"{s}: the page never showed {misses} of its sampled frames")
        b.close()

    print(f"{'song':>4} {'frames':>7} {'max mean':>9} {'bad px':>7} {'missed':>7}")
    for s, n, worst, px, misses in rows:
        flag = "" if (px <= PAGE_MAX and not misses) else "   <-- CHECK"
        print(f"{s:4d} {n:7d} {worst:9.2f} {px:7d} {misses:7d}{flag}")
    print("FAILED:", "; ".join(bad) if bad else "none")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
