"""Are all the frames there, at the film's own rate - and does the loop join up?

The clip has to carry every frame of its loop window at 30 fps: dropping frames
is what makes hand-drawn motion read as a slideshow.  This checks, per song,
that the encoded clip's frame count and rate match the window it was cut from.

It also checks the wrap.  A clip that loops is only seamless if the step from
its last frame back to its first is an ordinary frame step; anything much larger
is a cut, and the viewer sees the whole picture jump every loop.  The step is
measured on the clip as served, at a quarter size (the frames differ by far
more than codec noise), and compared with the largest ordinary step inside the
clip.

One clip is allowed its cut: song 10's scene never returns anywhere in its
segment (the best window still wraps at 36 against a step of 12), and the
forward loop's brief jump was preferred over a reversed clip.  The measured
value is recorded below, so the song is held to the cut it has - a regression
still fails.
"""
import glob
import json
import subprocess
import tempfile

import cv2
import numpy as np

W = json.load(open("_frames/art_windows.json"))
C = json.load(open("_frames/crops.json"))

SLACK = 1.5      # how far past the largest ordinary step the wrap may sit
FLOOR = 1.0      # ... with this much room, for drawings that barely move
# song -> the seam its loop is allowed (measured on the clip as served).  Only
# song 10: its scene never returns, and the cut was chosen over reversing it.
ACCEPTED_CUTS = {10: 32.0}
THUMB = "270:400"

bad = []
print(f"{'song':>4} {'window':>7} {'clip':>6} {'fps':>6} {'seam':>6} {'step':>6} {'ok':>4}")
for s in range(1, 13):
    src = "web/" + C[str(s)]["src"].split("?")[0]
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-count_frames", "-show_entries",
                          "stream=nb_read_frames,r_frame_rate,duration",
                          "-of", "json", src], capture_output=True, text=True, check=True)
    st = json.loads(out.stdout)["streams"][0]
    n = int(st["nb_read_frames"])
    num, den = st["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    L = W[str(s)]["length"]
    want = L

    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                        "-vf", f"scale={THUMB}", "-pix_fmt", "bgr24",
                        f"{td}/%04d.png"], check=True)
        ims = [cv2.imread(f) for f in sorted(glob.glob(f"{td}/*.png"))]
    steps = [float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())
             for a, b in zip(ims, ims[1:])]
    seam = float(np.abs(ims[-1].astype(np.int16) - ims[0].astype(np.int16)).mean())
    lim = max(SLACK * max(steps), FLOOR)
    if s in ACCEPTED_CUTS:
        lim = max(lim, ACCEPTED_CUTS[s] * 1.1)      # it may not get worse

    problems = []
    if n != want:
        problems.append(f"{n} frames, window wants {want}")
    if abs(fps - 30) > 0.1:
        problems.append(f"{fps:.1f} fps")
    if seam > lim:
        problems.append(f"the wrap is a cut ({seam:.1f} against a step of {max(steps):.1f})")
    if problems:
        bad.append(s)
    note = "  (accepted cut)" if s in ACCEPTED_CUTS else ""
    print(f"{s:4d} {want:7d} {n:6d} {fps:6.1f} {seam:6.2f} {max(steps):6.2f} "
          f"{'ok' if not problems else 'MISMATCH'}"
          + ("" if not problems else "  " + "; ".join(problems)) + note)
print("FAILED:", ("song " + ", ".join(map(str, bad))) if bad else "none")
raise SystemExit(1 if bad else 0)
