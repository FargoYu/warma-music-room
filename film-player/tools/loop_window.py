"""Pick each song's loop window so the wrap is an ordinary frame step.

The film's animation is periodic (the only non-periodic parts - the knob and the
elapsed clock - are erased from the art layer).  A loop is seamless when the
frame that would follow the last one is the frame before the first: that is, when
the window is a whole number of periods long.  So instead of taking the segment
as given and cross-fading its ends - which blends two different moments and
shows a ghost - this searches the window's start and its length together for the
pair whose wrap is closest to an ordinary frame-to-frame step.
"""
import json

import cv2
import numpy as np

SEG = json.load(open("_frames/segments.json"))
CL = json.load(open("_frames/clock_left_final.json"))
BAR = {1:(182,1355,897,1362), 2:(180,1357,899,1363), 3:(181,1356,899,1362),
       4:(180,1356,898,1362), 5:(182,1356,897,1362), 6:(181,1356,898,1362),
       7:(181,1356,901,1362), 8:(182,1356,900,1362), 9:(182,1355,900,1362),
       10:(180,1355,889,1362), 11:(182,1356,901,1362), 12:(184,1356,899,1362)}
HEAD_TRIM, TAIL_TRIM = 9, 6
SCALE = 4                       # the search runs on quarter-size frames
MIN_LEN, MAX_LEN = 90, 200


H, W = len(range(0, 1894, SCALE)), len(range(0, 1080, SCALE))


def mask(s):
    m = np.ones((H, W), bool)
    bx0, by0, bx1, by1 = BAR[s]
    m[max(0, (by0 - 34) // SCALE):(by1 + 34) // SCALE, bx0 // SCALE:bx1 // SCALE] = False
    x0, y0, x1, y1 = CL[str(s)]
    m[max(0, (y0 - 16) // SCALE):(y1 + 16) // SCALE, max(0, (x0 - 16) // SCALE):(x1 + 16) // SCALE] = False
    return m


plan = {}
for s in range(1, 13):
    a, b = SEG[str(s)]
    a, b = a + HEAD_TRIM, b - TAIL_TRIM
    n = b - a
    m = mask(s)
    small = []
    for i in range(a, b):
        im = cv2.imread(f"_frames/v/{i:04d}.jpg", cv2.IMREAD_GRAYSCALE)
        small.append(im[::SCALE, ::SCALE][m].astype(np.float32))
    step = float(np.mean([np.abs(small[i] - small[i + 1]).mean() for i in range(min(20, n - 1))]))

    best = None
    for L in range(MIN_LEN, min(MAX_LEN, n - 1) + 1):
        for o in range(0, n - L - 1):
            # the wrap goes from the last frame back to the first, so the frame
            # after the last must look like the frame before the first
            d = float(np.abs(small[o + L - 1] - small[o - 1]).mean()) if o > 0 else 1e9
            if best is None or d < best[0]:
                best = (d, o, L)
    d, o, L = best
    plan[s] = dict(start=int(a + o), length=int(L), seam=round(d, 3),
                   step=round(step, 3), ratio=round(d / max(step, 1e-3), 2), n=n)
    print(f"{s:2d} n={n:4d} -> start {o:3d} len {L:3d} seam {d:5.2f} "
          f"step {step:5.2f} ratio {d/max(step,1e-3):4.2f}", flush=True)
json.dump({str(k): v for k, v in plan.items()}, open("_frames/loop_plan.json", "w"), indent=1)
