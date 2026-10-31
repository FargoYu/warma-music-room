"""Build the moving layer: the film's own frames, full frame, full rate.

The whole picture animates in the film - not just the character: the posters
pulse, the clouds sweep, the linework boils.  So the moving layer is the entire
frame rather than a cropped region (a crop shows a seam wherever content crosses
its edge, and leaves the area outside it frozen while the film flashes).

Every frame is prepared exactly like the still (tools/build_stills.py:prepare),
so the clip and the still agree pixel for pixel at frame zero, then encoded at
the film's own 30 fps in VP9 4:4:4 full range.  Chroma is not subsampled, so the
clip cannot reintroduce the block structure the source video carries, and full
range makes the browser's YUV->RGB land on the still's exact colours.
"""
import json
import os
import subprocess
import sys

import cv2

sys.path.insert(0, os.path.dirname(__file__))
import build_stills as bs

OUT = "web/assets/anim"


def encode(tmp, out, crf=18):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "30",
                    "-i", f"{tmp}/%04d.png",
                    "-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0",
                    "-row-mt", "1", "-pix_fmt", "yuv444p", "-color_range", "pc",
                    "-colorspace", "bt709", "-color_primaries", "bt709",
                    "-color_trc", "bt709", "-an", out], check=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
    meta = json.load(open("_frames/crops.json")) if os.path.exists("_frames/crops.json") else {}
    for s in only:
        a, L = bs.W[str(s)]["start"], bs.W[str(s)]["length"]
        pbox = bs.ba.knob_band(s)
        sil = bs.ba.knob_silhouette(s, a, a + L, pbox)
        tmp = f"_frames/tmpa_{s:02d}"
        os.makedirs(tmp, exist_ok=True)
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        for k in range(L):
            im = bs.prepare(s, a + k, sil, pbox)[:bs.ART_BOTTOM]
            cv2.imwrite(f"{tmp}/{k:04d}.png", im, [cv2.IMWRITE_PNG_COMPRESSION, 4])
        frames = L
        out = f"{OUT}/{s:02d}.webm"
        encode(tmp, out)
        # the prepared frames are about 1 GB for the twelve songs; keep only the
        # clip once it is encoded
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
        meta[str(s)] = {"src": f"assets/anim/{s:02d}.webm", "frames": int(frames)}
        print(f"{s:2d} {frames:3d}f  {os.path.getsize(out)/1e6:5.2f} MB  full frame", flush=True)
    tmpf = "_frames/crops.json.tmp"
    json.dump(meta, open(tmpf, "w"), indent=1)
    os.replace(tmpf, "_frames/crops.json")
    print("wrote _frames/crops.json")
