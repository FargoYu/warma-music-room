"""Does the live clock draw where, and what, the film's own clock draws?

The elapsed clock is one of four things the player draws itself.  The film
puts its four glyphs on four fixed x positions (measured per song), bottom-
aligned on one baseline, at a per-song cap height and ink colour.  This reads
the browser's own geometry for every glyph and checks all four at once:

  * the glyph sits on its measured slot x, not on an approximated spacing
  * it is bottom-aligned on the measured baseline
  * it is scaled to the song's cap height
  * the atlas cell behind it is the cell for the character that was asked for

so a wrong slot table, a wrong scale, a wrong baseline or a shuffled glyph
cannot pass.  Run with the static server up (tools/serve.py, port 8770).
"""
import json
import sys

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, "tools")
import build_data3 as bd       # the same palette the page is given

GEO = json.load(open("_frames/ui_geom.json"))
CLK = json.load(open("_frames/clock_left_final.json"))

FRAC = 0.5          # mid-song: every song's text is then four glyphs, m:ss
TOL = 0.6           # px, in the 1080-wide design space

JS = """([frac]) => {
  const t = window.TRACKS[window.__player.index];
  window.__player.preview(frac);
  const A = window.CLOCK_ATLAS;
  const c = t.clock, k = c.cap / A.cap;
  const total = Math.max(0, Math.floor(frac * t.shown));
  const text = Math.floor(total / 60) + ":" +
               String(total % 60).padStart(2, "0");
  const bits = [...document.querySelectorAll('#clockCur .bit')];
  // the phone is scaled and centred by CSS: measure in the design's own space
  const ph = document.getElementById('phone').getBoundingClientRect();
  return {phx: ph.left, phy: ph.top,
    text: text, ctl: t.ctl,
    slots: c.slots, bottom: c.bottom, k: k,
    atlas: {w: A.w, h: A.h}, cells: A.cells,
    got: bits.map((b) => {
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      const pos = (cs.webkitMaskPosition || cs.maskPosition || "");
      return { x: r.left - ph.left, y: r.bottom - ph.top, w: r.width, h: r.height, pos: pos };
    }),
  };
}"""

fails = 0

# The documented contrast floors, enforced (see CLAUDE.md): every ink the player
# draws is measured against the backdrop under its own box.  ctl's floor is 2:1
# by decision - the elapsed clock must be the colour of the film's painted total
# clock, and on these posters the film's own handwriting is what it is.
bad_floors = []
for i in range(1, 13):
    t = bd.tracks[i - 1]
    for name, colour, bg, floor in (
            ("live", t["live"], t["bg"], 3.0),
            ("ctl", t["ctl"], bd.cleared_bg(i, CLK[str(i)]), 2.0),
            ("play", t["play"], bd.cleared_bg(i, GEO[str(i)]["box"]["play"]), 3.0),
            ("heart", t["heart"], t["heartBg"], 3.0)):
        c = bd.contrast(colour, bg)
        if c + 1e-6 < floor:
            bad_floors.append(f"{i} {name} {colour} on {bg} {c:.2f} < {floor}")
if bad_floors:
    fails += 1
print("colour floors:", "ok  " + "live 3 / ctl 2 / play 3 / heart 3"
      if not bad_floors else "; ".join(bad_floors))

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1894})
    for s in range(1, 13):
        pg.goto(f"http://127.0.0.1:8770/index.html?t={s - 1}", wait_until="networkidle")
        pg.wait_for_function("window.__player")
        pg.evaluate("document.getElementById('phone').style.transform='scale(1)'")
        d = pg.evaluate(JS, [FRAC])
        bad = []
        if len(d["got"]) != len(d["text"]):
            bad.append(f"glyphs {len(d['got'])} != {len(d['text'])} for {d['text']!r}")
        for i, g in enumerate(d["got"]):
            if i >= len(d["text"]):
                break
            ch = d["text"][i]
            cell = d["cells"][ch]
            k = d["k"]
            if abs(g["x"] - d["slots"][i]) > TOL:
                bad.append(f"[{i}] {ch!r} x {g['x']:.1f} != slot {d['slots'][i]}")
            if abs(g["y"] - (d["bottom"] + 1)) > TOL:
                bad.append(f"[{i}] {ch!r} baseline {g['y']:.1f} != {d['bottom']+1}")
            if abs(g["w"] - cell["w"] * k) > TOL:
                bad.append(f"[{i}] {ch!r} width {g['w']:.1f} != {cell['w']*k:.1f}")
            # mask offset x must be -cell.x*k: this is the cell for THIS character
            try:
                mx = float(g["pos"].split()[0].replace("px", ""))
                my = float(g["pos"].split()[1].replace("px", ""))
            except (ValueError, IndexError):
                mx = my = None
            if mx is None or abs(mx - (-cell["x"] * k)) > TOL:
                bad.append(f"[{i}] {ch!r} mask x {g['pos']!r} != {-cell['x']*k:.1f}px")
            # the vertical term is what selects the cell's rows: without it a
            # digit is drawn from the wrong slice of the atlas, at the right
            # slot, and the coverage test cannot tell
            want_y = (cell["h"] - d["atlas"]["h"]) * k
            if my is None or abs(my - want_y) > TOL:
                bad.append(f"[{i}] {ch!r} mask y {g['pos']!r} != {want_y:.1f}px")
        # The glyphs must actually paint: the atlas's masks draw strokes, not
        # filled rectangles (an atlas whose cells lost their alpha reads as solid
        # blocks at exactly the right slots) and not nothing (a missing bitmap).
        try:
            shot = pg.screenshot()      # viewport: phx/phy are viewport offsets
            im = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)
            hx = d["ctl"].lstrip("#")
            bgr = np.array([int(hx[4:6], 16), int(hx[2:4], 16), int(hx[0:2], 16)],
                           np.int16)
            # per slot, not the union of them: the gaps between slots would
            # dilute a solid rectangle down to the coverage of a stroke.  A glyph
            # never fills its own cell; a cell without its mask does.
            covers = []
            for g in d["got"]:
                gx0 = int(d["phx"] + g["x"]); gx1 = int(d["phx"] + g["x"] + g["w"])
                gy0 = int(d["phy"] + g["y"] - g["h"]); gy1 = int(d["phy"] + g["y"])
                cell = im[gy0:gy1, gx0:gx1]
                if cell.size:
                    covers.append(float((np.abs(cell.astype(np.int16) - bgr)
                                         .sum(2) < 90).mean()))
            if not covers or max(covers) > 0.92 or min(covers) < 0.02:
                bad.append("clock glyph cells are solid blocks or blank "
                           f"(coverage {min(covers or [0]):.2f}-{max(covers or [0]):.2f})")
        except Exception as e:
            bad.append(f"clock pixels not read ({type(e).__name__})")

        status = "ok  " if not bad else "FAIL"
        # The elapsed clock reads the film's printed total, not the audio file's
        # length (song 6's audio runs 388 s against a printed 239 s).  preview()
        # above is not the playback path: this seeks, which is what timeupdate
        # renders, and the text must land on the film's axis.  The preview text
        # is first moved off the target so the guard in renderClock cannot make
        # a stale value pass.
        try:
            pg.wait_for_function("() => window.__player.audio.duration > 0", timeout=5000)
            pg.evaluate("() => window.__player.preview(0.2)")
            before = pg.evaluate(
                "() => document.getElementById('clockCur').dataset.text")
            pg.evaluate("() => { const p = window.__player;"
                        " p.audio.currentTime = p.audio.duration * 0.5; }")
            pg.wait_for_function(
                "(old) => document.getElementById('clockCur').dataset.text !== old",
                arg=before, timeout=5000)
            d2 = pg.evaluate("""() => {
              const p = window.__player, t = window.TRACKS[p.index];
              const fmt = (v) => Math.floor(v / 60) + ':' +
                                 String(v % 60).padStart(2, '0');
              const f = p.audio.currentTime / p.audio.duration;
              return {shown: document.getElementById('clockCur').dataset.text,
                      film: fmt(Math.floor(t.shown * f)),
                      audio: fmt(Math.floor(p.audio.currentTime))};
            }""")
            if d2["shown"] != d2["film"]:
                bad.append(f"timeupdate clock {d2['shown']} != film-mapped "
                           f"{d2['film']} (the audio's axis would read {d2['audio']})")
        except Exception as e:
            bad.append(f"timeupdate path not exercised ({type(e).__name__})")

        if bad:
            fails += 1
        print(f"{s:2d} {status} {d['text']}  " + ("; ".join(bad) if bad else ""))
    b.close()
print("FAILED:", fails or "none")
sys.exit(1 if fails else 0)
