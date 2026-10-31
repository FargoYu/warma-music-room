"""Where does each drawing return to itself?  The authority for the loop window.

The clip loops, the film does not: a song runs for minutes over a window of two
to five seconds, so the window has to join up with itself or every loop is a
hard cut - a flash of the whole picture, which is the one artefact a viewer
cannot mistake for the drawing's own boiling.

For each song this measures, for every candidate length d, how far frame
start+d-1 is from frame start (the frame the still is cut from), and how far two
ordinary neighbouring frames are from each other.  A length whose end differs
from its start by no more than an ordinary frame step is a window that joins up;
anything much above that is a cut.  The chosen length is the longest candidate
that stays within that bound, so the loop is as long as it can be without
flashing, and the largest-valued fallback if the drawing never returns.

It writes a proposal (`art_windows_seam.json`) and never the authority itself:
`art_windows.json` decides which window each song is cut from, and a re-run must
not silently invalidate the artwork cut from it.  Copy a proposal across by hand,
then rebuild the clips.
"""
import json
import sys

import cv2
import numpy as np

SRC = "_frames/v/%04d.jpg"
MIN, MAX = 30, 240       # a loop shorter than a second reads as a stutter
SLACK = 0.25             # how far past an ordinary frame step a seam may sit
FLOOR = 0.30             # ... with this much room, for drawings that barely move


def frame(k):
    im = cv2.imread(SRC % k)
    return None if im is None else im.astype(np.int16)


def step(a, L):
    """An ordinary frame-to-frame difference inside this window."""
    d = [np.abs(frame(a + i) - frame(a + i + 1)).mean() for i in (3, L // 3, L // 2, L - 4)
         if frame(a + i) is not None and frame(a + i + 1) is not None]
    return float(np.mean(d)) if d else 0.0


def main():
    W = json.load(open("_frames/art_windows.json"))
    only = [int(x) for x in sys.argv[1:]] or sorted(int(k) for k in W)
    out = {}
    print(f"{'song':>4} {'start':>6} {'was':>4} {'now':>4} {'seam':>6} {'step':>6} {'x':>5}")
    for s in only:
        a, old = W[str(s)]["start"], W[str(s)]["length"]
        f0 = frame(a)
        st = step(a, old)
        lim = max(FLOOR, st + SLACK)
        vals, good = {}, []
        d = MIN
        while d <= MAX:
            fj = frame(a + d - 1)
            if fj is None:
                break
            vals[d] = float(np.abs(fj - f0).mean())
            if vals[d] <= lim:
                good.append(d)
            d += 1
        if not vals:
            print(f"{s:4d} {a:6d} {old:4d} {'-':>4}  (no footage)")
            continue
        if good:
            new = max(good)
        else:
            best = min(vals.values())
            new = max(d for d, v in vals.items() if v <= best + 0.1)
        seam, ratio = vals[new], vals[new] / max(1e-6, st)
        out[str(s)] = {"start": a, "length": new,
                       "seam": round(seam, 2), "step": round(st, 2)}
        flag = "" if ratio <= 1.5 else "   <-- still a cut"
        print(f"{s:4d} {a:6d} {old:4d} {new:4d} {seam:6.2f} {st:6.2f} {ratio:5.1f}{flag}")
    json.dump(out, open("_frames/art_windows_seam.json", "w"), indent=1)
    print("wrote _frames/art_windows_seam.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
