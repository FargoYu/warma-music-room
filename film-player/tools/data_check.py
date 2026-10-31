"""Does the page carry the palette and geometry the build computed?

`web/js/data.js` is generated output. Nothing else proves the page received it:
every other check reads geometry from the page and colours from the builder, so
editing `build_data3.py` and forgetting to run it - or hand-editing `data.js` -
left every colour check green against a palette the page did not have.

This compares three things, per song:

  * the tracks the builder computes now (`build_data3.tracks`, including the
    asset mtime stamps),
  * the tracks the page parsed (`window.TRACKS`),
  * the colours the page actually paints with (`getComputedStyle` on the knob,
    the elapsed clock's spans, the play key and the heart's CSS variables).

and then measures the documented contrast floors on the page's own colours.
Run with the static server up (tools/serve.py, port 8770).
"""
import json
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, "tools")
import build_data3 as bd

URL = "http://127.0.0.1:8770/index.html?t=%d"

JS = """() => {
  const p = window.__player, t = window.TRACKS[p.index];
  const cs = (el) => getComputedStyle(el);
  const bits = document.querySelectorAll('#clockCur .bit');
  const hex = (el, prop) => {
    const v = cs(el)[prop];
    const m = /rgb\\((\\d+), (\\d+), (\\d+)\\)/.exec(v);
    return m ? '#' + [1, 2, 3].map((i) => (+m[i]).toString(16).padStart(2, '0')).join('').toUpperCase() : v;
  };
  const root = cs(document.getElementById('phone'));
  return {
    track: t,
    live: hex(document.getElementById('knob'), 'backgroundColor'),
    ctl: bits.length ? hex(bits[0], 'backgroundColor') : null,
    play: hex(document.getElementById('btnPlay'), 'color'),
    heart: root.getPropertyValue('--heart').trim().toUpperCase(),
    heartBg: root.getPropertyValue('--heart-bg').trim().toUpperCase(),
  };
}"""

only = [int(x) for x in sys.argv[1:]] or list(range(1, 13))
bad = []
print(f"{'song':>4} {'data.js':>8} {'live':>8} {'ctl':>8} {'play':>8} {'floor':>6}")
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1600})
    for s in only:
        want = bd.tracks[s - 1]
        pg.goto(URL % (s - 1), wait_until="domcontentloaded")
        pg.wait_for_function("window.__player && window.TRACKS")
        got = pg.evaluate(JS)
        page = got["track"]
        problems = []

        # 1. the page's copy of the generated data, field for field
        if json.dumps(page, sort_keys=True) != json.dumps(want, sort_keys=True):
            keys = [k for k in want if page.get(k) != want[k]]
            problems.append("data.js is not what build_data3 computes (" +
                            ", ".join(keys) + ")")

        # 2. the colours the page actually paints with
        for key in ("live", "ctl", "play", "heart", "heartBg"):
            if got[key] is None:
                problems.append(f"{key} is not painted")
            elif got[key] != want[key].upper():
                problems.append(f"{key} paints {got[key]}, data.js says {want[key]}")

        # 3. the documented floors, on the page's colours
        def contrast(a, b):
            return bd.contrast(a.lower(), b.lower())
        floors = [
            ("live", want["live"], want["bg"], 3.0),
            ("ctl", want["ctl"], bd.cleared_bg(s, bd.CLOCK[str(s)]), 2.0),
            ("play", want["play"], bd.cleared_bg(s, bd.GEOM[str(s)]["box"]["play"]), 3.0),
            ("heart", want["heart"], want["heartBg"], 3.0),
        ]
        worst = min((contrast(c, bg) for _, c, bg, _ in floors), default=99)
        for name, c, bg, floor in floors:
            if contrast(c, bg) + 1e-6 < floor:
                problems.append(f"{name} {c} on {bg} is {contrast(c, bg):.2f} < {floor}")

        if problems:
            bad.append(s)
        status = "ok" if not problems else "FAIL"
        print(f"{s:4d} {status:>6} {want['live']:>8} {want['ctl']:>8} "
              f"{want['play']:>8} {worst:6.2f}"
              + ("" if not problems else "  " + "; ".join(problems)))
    b.close()

print("FAILED:", ("song " + ", ".join(map(str, bad))) if bad else "none")
sys.exit(1 if bad else 0)
