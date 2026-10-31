"""Every frame, against the film frame it came from.

Only the elements the player animates (knob, elapsed clock, play key, the
transport row's ink, the cropped-off watermark strip) are allowed to differ, so
this masks exactly those and compares the rest pixel by pixel, frame by frame.
A frame that fails here is a frame the viewer will see as wrong.
"""
import json
import os
import subprocess
import tempfile
import sys

import cv2
import numpy as np

sys.path.insert(0, "tools")
import build_stills as bs

W = json.load(open("_frames/art_windows.json"))
C = json.load(open("_frames/crops.json"))
CL = json.load(open("_frames/clock_left_final.json"))
GEOM = json.load(open("_frames/ui_geom.json"))
H = bs.ART_BOTTOM
TOL = 8.0      # a frame's mean difference, codec noise included
BAD = 40       # per-pixel difference that is a real defect
BAD_MAX = 400  # how many such pixels a frame may carry: a mean alone lets a
               # 200x200 patch from the wrong frame (~2.7 over the whole mask) pass


def keep_mask(s):
    m = np.ones((H, 1080), bool)
    bx0, by0, bx1, by1 = bs.BAR[s]
    m[max(0, by0 - 60):min(H, by1 + 60), max(0, bx0 - 70):min(1080, bx1 + 70)] = False
    x0, y0, x1, y1 = CL[str(s)]
    m[max(0, y0 - 20):min(H, y1 + 20), max(0, x0 - 20):min(1080, x1 + 20)] = False
    # play and heart are erased and drawn live; prev and next are recoloured in
    # the still and the clip (the transport ink moved to a readable colour)
    for key in ("play", "heart", "prev", "next"):
        pb = GEOM[str(s)]["box"][key]
        m[max(0, pb[1] - 8):min(H, pb[3] + 8), max(0, pb[0] - 8):min(1080, pb[2] + 8)] = False
    m = m.copy()
    m[1786:] = False                       # cropped off entirely
    return m


def main():
    only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
    rows = []
    for s in only:
        a, L = W[str(s)]["start"], W[str(s)]["length"]
        n = L
        m = keep_mask(s)
        # decode with ffmpeg so the YUV->RGB conversion honours the clip's tags:
        # OpenCV assumes BT.601, which shifts saturated colours by ~20 levels
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["ffmpeg", "-y", "-v", "error",
                            "-i", "web/" + C[str(s)]["src"].split("?")[0],
                            "-vf", "scale=in_color_matrix=bt709:in_range=pc:out_range=pc",
                            "-pix_fmt", "bgr24", f"{td}/%04d.png"], check=True)
            per = []
            for k in range(n):
                got = cv2.imread(f"{td}/{k + 1:04d}.png")
                if got is None:
                    per.append((999.0, k, "missing frame"))
                    break
                src = cv2.imread(f"_frames/v/{a + k:04d}.jpg")[:H]
                d = np.abs(got.astype(np.int16) - src.astype(np.int16)).max(2)
                per.append((float(d[m].mean()), k, int(((d > BAD) & m).sum())))
        vals = [p[0] for p in per]
        worst = max(per)
        worst_px = max(per, key=lambda p: p[2])
        rows.append((s, n, float(np.mean(vals)), float(np.percentile(vals, 99)),
                     worst[0], worst[1], worst_px[2], worst_px[1]))

    print(f"{'song':>4} {'frames':>7} {'mean':>6} {'p99':>6} {'worst':>6} "
          f"{'at frame':>9} {'bad px':>7}")
    bad = []
    for s, L, mean, p99, mx, k, px, pxk in rows:
        flag = "" if (mx < TOL and px <= BAD_MAX) else "   <-- CHECK"
        if mx >= TOL:
            bad.append(f"{s}: frame {k} differs by {mx:.1f} (limit {TOL:.0f})")
        if px > BAD_MAX:
            bad.append(f"{s}: frame {pxk} has {px} px off by more than {BAD} "
                       f"(ceiling {BAD_MAX})")
        print(f"{s:4d} {L:7d} {mean:6.2f} {p99:6.2f} {mx:6.2f} {k:9d} {px:7d}{flag}")
    print("FAILED:", "; ".join(bad) if bad else "none")
    sys.exit(1 if bad else 0)



if __name__ == '__main__':
    sys.exit(main())
