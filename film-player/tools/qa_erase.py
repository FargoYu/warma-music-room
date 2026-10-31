"""The two things the artwork must not contain, frame by frame.

The player draws the knob and the elapsed clock itself, so neither may be left
in the artwork - and the eraser must not do its work on some frames and not
others, because the clip plays that difference as a flicker.  Both are checked
here against the clip as served, not against the intermediate images:

  * knob    - in the knob's own window the clip must differ from the film frame
              it was cut from: the film has a knob there and the clip must not.
              Counting differing pixels over the footprint is what proves the
              erasure happened on *that* frame; looking for ink cannot, because
              the knob is filled in a colour that is not the song's ink, so a
              leftover knob still passes an ink test on most posters.  The
              song-wide silhouette is widened by the knob's own travel, so the
              song-wide share is taken over the silhouette *intersected with
              every place the film ever draws the knob*: the widened shape alone
              counts empty backdrop as survivor and read song 10 at 0.29 against
              a 0.35 floor while its per-frame share was 0.63.
  * ink     - no ink run taller than the bar line stands anywhere in the knob's
              column window, which is what a half-erased knob's outline leaves.
  * rebuild - the rebuilt patch must not move differently from the band around
              it.  A patch that appears, vanishes or smears on a few frames
              spikes here while the surrounding band stays quiet.

The band and the silhouette are located the way the builder locates them, but
both measurements are made against the film, not against anything the eraser
produced: a reference the eraser wrote cannot catch the eraser.
"""
import json
import subprocess
import sys
import tempfile

import cv2
import numpy as np

sys.path.insert(0, "tools")
import build_stills as bs
import build_art7 as ba

W = json.load(open("_frames/art_windows.json"))
C = json.load(open("_frames/crops.json"))
CL = json.load(open("_frames/clock_left_final.json"))
HAND = json.load(open("_frames/clock_ink.json"))    # the handwriting's measured ink

RUN_MAX = 16.0      # the bar line is 8 px; the knob is 23-41 px tall
ERASED = 0.35       # of the film's knob footprint, this much must no longer match
FRAME_ERASED = 0.60 # the same, measured on the knob as *that frame* draws it: the
                    # song-wide silhouette is the eraser's own idea of the knob,
                    # so measuring only inside it cannot see a knob that sits
                    # outside it on some frames
INK_TOL = 110.0     # summed BGR distance that still counts as the same ink
DIFF = 30           # per-pixel difference that is the knob gone, not codec noise
CLOCK_MIN = 0.25    # the clock is erased on every frame, or on none: a frame
                    # that shows far less removal than the song's median is a
                    # frame the handwriting survived on
CLOCK_ABS = 5.0     # how much the clip's clock box must differ from the film's:
                    # codec noise alone is a fraction of this, so a check that
                    # only compares frames against each other would not notice
                    # an eraser that never ran
SPIKE_MAX = 2.6     # the patch may not move this much faster than its neighbours
CLOCK_LEFT = 0.15   # of the film's strongest ink pixels, the share that may still
                    # match the film within CLOCK_TOL: a mean over the box passes
                    # a hand that kept a digit
CLOCK_TOL = 12      # a difference this small is the stroke still there
CLOCK_VISIBLE = 30  # the handwriting must stand at least this far (one channel)
                    # off the box's backdrop before the question is answerable:
                    # on song 10 the film's own clock is fainter than the cloud
                    # behind it, and a surviving stroke there is invisible too
SPIKE_ABS = 1.0     # ... once the patch moves at all: on a drawing that sits
                    # still, a ratio of two near-zero motions is only noise


def tall_run(band, ink):
    """Longest vertical run of ink-coloured pixels, per column."""
    d = np.abs(band.astype(np.float32) - np.array(ink, np.float32)).sum(axis=2)
    m = d < INK_TOL
    best = np.zeros(band.shape[1], np.int32)
    for c in range(band.shape[1]):
        run = 0
        for v in m[:, c]:
            run = run + 1 if v else 0
            if run > best[c]:
                best[c] = run
    return best


def main():
    only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
    rows = []
    bad = []
    for s in only:
        a, L = W[str(s)]["start"], W[str(s)]["length"]
        pbox = ba.knob_band(s)
        y0, y1 = pbox[1], min(bs.ART_BOTTOM, pbox[3])
        sil = ba.knob_silhouette(s, a, a + L, pbox)
        if sil is None:
            bad.append(f"{s}: no knob silhouette")
            rows.append((s, L, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
            continue
        ys, xs = np.nonzero(sil)
        cx_sil = float((xs.min() + xs.max()) / 2)
        # the window the eraser rebuilt, in band coordinates and on the frame
        w0, w1 = int(xs.min()) - 2, int(xs.max()) + 3
        ink = ba.INK[s]
        h = y1 - y0
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["ffmpeg", "-y", "-v", "error",
                            "-i", "web/" + C[str(s)]["src"].split("?")[0],
                            "-vf", f"crop=1080:{h}:0:{y0},"
                                   "scale=in_color_matrix=bt709:in_range=pc:out_range=pc",
                            "-pix_fmt", "bgr24", f"{td}/%04d.png"], check=True)
            # is the film's handwriting even distinguishable in its box?
            cxo, cyo, cxe, cye = CL[str(s)]
            f0 = ba.read(a)[cyo:cye, cxo:cxe].astype(np.float32)
            r0 = np.concatenate([f0[0], f0[-1], f0[:, 0], f0[:, -1]])
            hc = HAND[str(s)]
            hand = np.array([int(hc[5:7], 16), int(hc[3:5], 16), int(hc[1:3], 16)],
                            np.float32)
            judge = bool(np.abs(hand - np.median(r0, axis=0)).max() >= CLOCK_VISIBLE)

            worst_run, worst_k = 0.0, 0
            frame_gone, frame_k = 1.0, 0
            seen = 0
            # the song-wide silhouette is widened by the knob's measured travel,
            # so on most frames part of it is empty backdrop - pixels that match
            # the film because no knob was drawn there.  The erasure is measured
            # over the silhouette intersected with every place the film ever
            # draws the knob (the union of the per-frame masks), which is the
            # question the check means to ask.
            union = np.zeros_like(sil, bool)
            band_d = []
            clk = []
            clk_resid, clk_resid_k = 0.0, 0
            prev = None
            patch, ref = [], []
            for k in range(L):
                band = cv2.imread(f"{td}/{k + 1:04d}.png")
                if band is None:
                    bad.append(f"{s}: frame {k} missing")
                    break
                full = ba.read(a + k)
                film = full[y0:y1]
                if film is None or film.shape[:2] != band.shape[:2]:
                    bad.append(f"{s}: frame {k} is not the film frame it came from")
                    break
                # only the knob's own column window is the eraser's responsibility
                r = float(tall_run(band, ink)[w0:w1].max())
                if r > worst_run:
                    worst_run, worst_k = r, k
                d = np.abs(band.astype(np.int16) - film.astype(np.int16)).max(2)
                # the knob as this frame draws it, found independently of the
                # silhouette the eraser used
                near = [c for c in ba.knob_candidates(full, s, pbox)
                        if abs(c["cx"] - cx_sil) < 25]
                dk = d[:, pbox[0]:pbox[0] + sil.shape[1]]
                band_d.append(dk)
                if near:
                    seen += 1
                    mk = max(near, key=lambda c: c["area"])["mask"] > 0
                    union |= mk
                    gone_f = float((dk[mk] > DIFF).mean())
                    if gone_f < frame_gone:
                        frame_gone, frame_k = gone_f, k
                cxo, cyo, cxe, cye = CL[str(s)]
                # the clock box lies inside the band, so it costs no extra decode
                dc = d[cyo - y0:cye - y0, cxo:cxe]
                clk.append(float(dc.mean()))
                # The handwriting is drawn afresh every frame; its strongest
                # pixels must not match the film, or a digit survives.  The
                # strongest are the top decile of "differs from the box's own
                # backdrop" - no colour mask, which on faint posters selects the
                # background as readily as the strokes.
                roi = film[cyo - y0:cye - y0, cxo:cxe].astype(np.float32)
                ring = np.concatenate([roi[0], roi[-1], roi[:, 0], roi[:, -1]])
                off = np.abs(roi - np.median(ring, axis=0)).max(2)
                mk = off >= np.percentile(off, 90)
                if judge and mk.any():
                    resid = float((dc[mk] <= CLOCK_TOL).mean())
                    if resid > clk_resid:
                        clk_resid, clk_resid_k = resid, k
                if prev is not None:
                    dd = np.abs(band.astype(np.int16) - prev.astype(np.int16)).mean(axis=2)
                    patch.append(float(dd[:, w0:w1].mean()))
                    ref.append(float(np.delete(dd, np.s_[max(0, w0 - 200):w1 + 200],
                                               axis=1).mean()))
                prev = band
        foot = (sil > 0)
        if union.any():
            foot &= union
        erased, erased_k = 1.0, 0
        for k, dk in enumerate(band_d):
            if not foot.any():
                break
            g = float((dk[foot] > DIFF).mean())
            if g < erased:
                erased, erased_k = g, k
        pm, rm = float(np.mean(patch)), float(np.mean(ref))
        spike = pm / max(1e-6, rm)
        cmin, cmed = min(clk), float(np.median(clk))
        rows.append((s, L, erased, worst_run, frame_gone, cmin, cmed, pm, rm, spike))
        if erased < ERASED:
            bad.append(f"{s}: the film's knob is still in the clip at frame {erased_k} "
                       f"({erased:.2f} of it gone)")
        if worst_run > RUN_MAX:
            bad.append(f"{s}: knob ink left in the band (run {worst_run:.0f}px at frame {worst_k})")
        if cmed < CLOCK_ABS:
            bad.append(f"{s}: the clock box is not the film's handwriting erased "
                       f"({cmed:.2f} against a floor of {CLOCK_ABS:.1f})")
        if cmed > 0.2 and cmin < CLOCK_MIN * cmed:
            bad.append(f"{s}: the clock is erased on some frames and not others "
                       f"({cmin:.2f} against a median of {cmed:.2f})")
        # the per-frame test is only a test if it found the knob at all: with no
        # candidates every frame the loop above is a no-op that reads 1.00
        if not seen:
            bad.append(f"{s}: the per-frame knob test found no knob on any frame")
        if frame_gone < FRAME_ERASED:
            bad.append(f"{s}: the knob is still there on frame {frame_k} as that "
                       f"frame draws it ({frame_gone:.2f} erased)")
        if judge and clk_resid > CLOCK_LEFT:
            bad.append(f"{s}: the film's clock ink still matches on frame "
                       f"{clk_resid_k} ({clk_resid:.0%} of it, ceiling "
                       f"{CLOCK_LEFT:.0%})")
        if pm > SPIKE_ABS and spike > SPIKE_MAX:
            bad.append(f"{s}: rebuilt patch moves {spike:.2f}x faster than the band "
                       f"({pm:.2f} vs {rm:.2f})")

    print(f"{'song':>4} {'frames':>7} {'gone':>6} {'per frame':>10} {'tall run':>9} "
          f"{'clock':>11} {'patch':>7} {'band':>6} {'x':>5}")
    for s, L, erased, run, frame_gone, cmin, cmed, pm, rm, spike in rows:
        ok = (erased >= ERASED and frame_gone >= FRAME_ERASED and run <= RUN_MAX
              and cmed >= CLOCK_ABS
              and not (cmed > 0.2 and cmin < CLOCK_MIN * cmed)
              and not (pm > SPIKE_ABS and spike > SPIKE_MAX))
        print(f"{s:4d} {L:7d} {erased:6.2f} {frame_gone:10.2f} {run:9.1f} "
              f"{cmin:5.2f}/{cmed:5.2f} {pm:7.2f} {rm:6.2f} {spike:5.2f}"
              f"{'' if ok else '   <-- CHECK'}")
    print("FAILED:", "; ".join(bad) if bad else "none")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
