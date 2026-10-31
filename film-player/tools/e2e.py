"""End-to-end check of the player in a real browser.

Exercises the things a user does: play, pause, seek by clicking the bar, drag the
knob, switch tracks with the transport buttons, open the list sheet and pick a
track, and the keyboard shortcuts.  Fails loudly if any of it does not work.
"""
import json
import cv2
import numpy as np
import sys

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8770/index.html"
fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + str(detail)) if detail else ""))
    if not cond:
        fails.append(name)


with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 1080, "height": 1894})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_function("window.__player && document.getElementById('pic0').complete")

    st = pg.evaluate("""() => {
      const p = window.__player;
      return {index: p.index, paused: p.audio.paused, src: p.audio.currentSrc};
    }""")
    check("starts on track 1", st["index"] == 0, st)
    check("starts paused", st["paused"], st)
    check("the play key is named for what it will do", pg.evaluate(
        "() => document.getElementById('btnPlay').getAttribute('aria-label')") == "播放")

    pg.click("#btnPlay")
    # the clip and the audio both have to load before playback really starts
    pg.wait_for_function("() => window.__player.audio.currentTime > 0.3", timeout=8000)
    st = pg.evaluate("""() => ({paused: window.__player.audio.paused,
                                t: window.__player.audio.currentTime,
                                live: window.__player.pics.classList.contains("live"),
                                cropShown: !document.getElementById('crop').hidden})""")
    check("play starts audio", not st["paused"] and st["t"] > 0.3, st)
    check("play starts the drawing cycle", st["live"] and st["cropShown"], st)

    pg.wait_for_timeout(800)
    t1 = pg.evaluate("() => window.__player.audio.currentTime")
    check("audio advances", t1 > 1.0, t1)

    # The key's glyphs: the film never shows a pause state, so the bars are the
    # player's own drawing and nothing else looks at them.  A triangle has ink
    # in the middle of its box; two bars have a gap there (measured 0.4-0.5 vs
    # 0.0).
    def key_mid_ink():
        shot = pg.query_selector("#btnPlay").screenshot()
        im = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)
        c = pg.evaluate("() => window.TRACKS[window.__player.index].play").lstrip("#")
        bgr = np.array([int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16)], np.int16)
        ink = np.abs(im.astype(np.int16) - bgr).sum(2) < 160
        w = ink.shape[1]
        return float(ink[:, w // 2 - 2:w // 2 + 3].mean())      # the gap between bars

    mid_playing = key_mid_ink()
    check("the key shows two bars while playing", mid_playing < 0.02, round(mid_playing, 3))

    # The knob is driven from timeupdate during playback; the seek check below
    # is a different path (preview()/seekFromEvent), so a timeupdate handler
    # that stopped moving the knob would pass all of them.  Two samples: the
    # knob sits at the audio's fraction, and it moved between them.
    KNOB_JS = r"""() => {
      const p = window.__player;
      const m = /translateX\(([-\d.]+)px\)/
        .exec(document.getElementById('knob').style.transform);
      return {x: m ? parseFloat(m[1]) : NaN,
              w: document.getElementById('bar').clientWidth,
              f: p.audio.currentTime / p.audio.duration};
    }"""
    k1 = pg.evaluate(KNOB_JS)
    pg.wait_for_timeout(700)
    k2 = pg.evaluate(KNOB_JS)
    check("the knob follows playback",
          k1["w"] > 0 and abs(k1["x"] / k1["w"] - k1["f"]) < 0.05, k1)
    check("the knob moves while the song plays", k2["x"] > k1["x"], (k1["x"], k2["x"]))

    # the moving region has to actually change on screen: compare two shots of
    # the same rectangle while the song plays
    clip = {"x": 0, "y": 300, "width": 1080, "height": 700}   # the artwork
    a = pg.screenshot(clip=clip)
    pg.wait_for_timeout(450)
    b2 = pg.screenshot(clip=clip)
    import io as _io
    import numpy as _np
    import cv2 as _cv2
    ia = _cv2.imdecode(_np.frombuffer(a, _np.uint8), _cv2.IMREAD_COLOR).astype(_np.int16)
    ib = _cv2.imdecode(_np.frombuffer(b2, _np.uint8), _cv2.IMREAD_COLOR).astype(_np.int16)
    moved = float(_np.abs(ia - ib).mean())
    check("the moving region changes on screen while the song plays", moved > 0.2, round(moved, 2))

    pg.click("#btnPlay")
    pg.wait_for_timeout(200)
    st = pg.evaluate("() => ({paused: window.__player.audio.paused, t: window.__player.audio.currentTime, "
                     "live: window.__player.pics.classList.contains('live'), "
                     "cropShown: !document.getElementById('crop').hidden})")
    check("pause stops audio", st["paused"], st)
    mid_paused = key_mid_ink()
    check("the key shows its triangle when paused", mid_paused > 0.2, round(mid_paused, 3))
    check("pause keeps the drawing on screen", st["cropShown"] and not st["live"], st)
    frozen_ct = pg.evaluate("() => document.getElementById('crop').currentTime")
    check("the frozen drawing is not the clip's first frame", frozen_ct > 0.1,
          round(frozen_ct, 2))
    pg.wait_for_timeout(450)
    f1 = pg.screenshot(clip=clip)
    pg.wait_for_timeout(450)
    f2 = pg.screenshot(clip=clip)
    ia = _cv2.imdecode(_np.frombuffer(f1, _np.uint8), _cv2.IMREAD_COLOR).astype(_np.int16)
    ib = _cv2.imdecode(_np.frombuffer(f2, _np.uint8), _cv2.IMREAD_COLOR).astype(_np.int16)
    check("the paused drawing is frozen", float(_np.abs(ia - ib).mean()) < 0.05,
          round(float(_np.abs(ia - ib).mean()), 3))

    # seek by clicking the bar at 50%
    box = pg.query_selector("#bar").bounding_box()
    pg.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
    pg.wait_for_timeout(300)
    st = pg.evaluate("""() => ({t: window.__player.audio.currentTime,
                                d: window.__player.audio.duration,
                                knob: document.getElementById('knob').style.transform})""")
    frac = st["t"] / st["d"]
    check("click seeks to half", 0.4 < frac < 0.6, round(frac, 3))
    check("knob follows the seek", "0.5" in st["knob"] or abs(float(st["knob"].split("(")[1].split("p")[0]) / pg.evaluate("() => document.getElementById('bar').clientWidth") - 0.5) < 0.05, st["knob"])

    # the bar is a slider: it reports its own value, and with the keyboard focus
    # on it the arrows scrub instead of skipping the track
    st = pg.evaluate("""() => {
      const b = document.getElementById('bar');
      return {role: b.getAttribute('role'), text: b.getAttribute('aria-valuetext'),
              now: b.getAttribute('aria-valuenow')};
    }""")
    check("the bar is a slider with a readable value",
          st["role"] == "slider" and "/" in st["text"] and 40 <= int(st["now"]) <= 60, st)
    t0 = pg.evaluate("() => window.__player.audio.currentTime")
    i0 = pg.evaluate("() => window.__player.index")
    pg.focus("#bar")
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(200)
    t1 = pg.evaluate("() => window.__player.audio.currentTime")
    check("the bar's arrows scrub it", 3.5 < t1 - t0 < 6.5
          and pg.evaluate("() => window.__player.index") == i0, (round(t0, 2), round(t1, 2)))

    # a real drag, not a click: press on the bar, move across it, release.  The
    # pointermove path and its throttle are exercised by nothing else.
    box = pg.query_selector("#bar").bounding_box()
    y = box["y"] + box["height"] / 2
    pg.mouse.move(box["x"] + box["width"] * 0.2, y)
    pg.mouse.down()
    for f in (0.35, 0.5, 0.65, 0.8):
        pg.mouse.move(box["x"] + box["width"] * f, y, steps=3)
    during = pg.evaluate("() => document.getElementById('knob').style.transform")
    pg.mouse.up()
    pg.wait_for_timeout(300)
    st = pg.evaluate("() => ({t: window.__player.audio.currentTime,"
                     " d: window.__player.audio.duration})")
    check("a drag scrubs the song", abs(st["t"] / st["d"] - 0.8) < 0.06
          and "translateX" in during, (round(st["t"] / st["d"], 2), during))

    # next / prev
    pg.click("#btnNext")
    pg.wait_for_timeout(600)
    check("next goes to track 2", pg.evaluate("() => window.__player.index") == 1)
    pg.click("#btnPrev")
    pg.wait_for_timeout(600)
    check("prev goes back to track 1", pg.evaluate("() => window.__player.index") == 0)

    # mid-song, "previous" means "play it again"; only at the start does it step
    # back a track
    box = pg.query_selector("#bar").bounding_box()
    pg.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
    pg.wait_for_timeout(300)
    check("the song is under way for the restart rule",
          pg.evaluate("() => window.__player.audio.currentTime") > 3)
    pg.click("#btnPrev")
    pg.wait_for_timeout(400)
    st = pg.evaluate("() => ({i: window.__player.index, t: window.__player.audio.currentTime})")
    check("prev restarts a song that is under way", st["i"] == 0 and st["t"] < 1.0, st)
    pg.click("#btnPrev")
    pg.wait_for_timeout(600)
    check("prev at the start steps back a track",
          pg.evaluate("() => window.__player.index") == 11)

    # list sheet
    pg.click("#btnList")
    pg.wait_for_timeout(400)
    check("list sheet opens", pg.evaluate("() => document.getElementById('sheet').classList.contains('open')"))
    check("list has 12 tracks", pg.evaluate("() => document.querySelectorAll('#list li').length") == 12)
    pg.click("#list li:nth-child(5)")
    pg.wait_for_timeout(700)
    check("picking a track loads it", pg.evaluate("() => window.__player.index") == 4)
    check("sheet closes after pick", not pg.evaluate("() => document.getElementById('sheet').classList.contains('open')"))
    check("drawings follow the track",
          "/05_0.png" in pg.evaluate("() => document.getElementById('pic0').src")
          and "/05.webm" in pg.evaluate("() => document.getElementById('crop').src"),
          pg.evaluate("() => document.getElementById('crop').src"))

    check("the media session names the track", pg.evaluate(
        "() => navigator.mediaSession && navigator.mediaSession.metadata"
        " ? navigator.mediaSession.metadata.title : null") == "甜蜜魔法")

    # keyboard
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(500)
    check("ArrowRight advances", pg.evaluate("() => window.__player.index") == 5)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    was = pg.evaluate("() => window.__player.audio.paused")
    pg.keyboard.press(" ")
    pg.wait_for_timeout(500)
    check("Space toggles playback when no control has focus",
          pg.evaluate("() => window.__player.audio.paused") != was)
    pg.keyboard.press(" ")
    pg.wait_for_timeout(300)

    # a focused key keeps Space for itself, and Escape gives the focus back
    pg.click("#dots")
    pg.wait_for_timeout(200)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    check("Escape puts focus back on the key that opened the panel",
          pg.evaluate("() => document.activeElement.id") == "dots")
    pg.keyboard.press(" ")
    pg.wait_for_timeout(200)
    check("Space activates the focused key rather than the transport",
          pg.evaluate("() => !document.getElementById('info').hidden"))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)


    # the play key points the way the film's own key points: the film's own
    # triangle is the ground truth, read from the same box in the film frame -
    # a missing flip rule is exactly how the mirrored keys used to break
    GEOM = json.load(open("_frames/ui_geom.json"))
    AW = json.load(open("_frames/art_windows.json"))

    def lean(im, box):
        x0, y0, x1, y1 = box
        roi = im[y0 + 2:y1 - 2, x0 + 2:x1 - 2].astype(float)
        ring = np.concatenate([roi[0], roi[-1], roi[:, 0], roi[:, -1]])
        ink = (np.abs(roi - np.median(ring, axis=0)).sum(2) > 40)
        return 1 if ink[:, :roi.shape[1] // 2].sum() < ink[:, roi.shape[1] // 2:].sum() else -1

    for song in (1, 7):
        pg.goto(f"http://127.0.0.1:8770/index.html?t={song - 1}",
                wait_until="domcontentloaded")
        pg.wait_for_function("document.getElementById('pic0').complete")
        pg.evaluate("document.getElementById('phone').style.transform='scale(1)'")
        shot = pg.query_selector("#phone").screenshot()
        page = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)[:1600, :1080]
        film = cv2.imread(f"_frames/v/{AW[str(song)]['start']:04d}.jpg")[:1600]
        box = GEOM[str(song)]["box"]["play"]
        check(f"play key {song} points where the film's does",
              lean(film, box) == lean(page, box))

        # the heart is drawn live inside the film's own heart box: its ink must
        # land on the film's heart, not float smaller inside a letterboxed svg
        def ink_mask(im, box):
            x0, y0, x1, y1 = box
            roi = im[y0 + 1:y1 - 1, x0 + 1:x1 - 1].astype(float)
            ring = np.concatenate([roi[0], roi[-1], roi[:, 0], roi[:, -1]])
            return np.abs(roi - np.median(ring, axis=0)).sum(2) > 60

        def ink_box(m):
            ys, xs = np.nonzero(m)
            if len(xs) < 20:
                return None
            return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

        hb = GEOM[str(song)]["box"]["heart"]
        mf, mp = ink_mask(film, hb), ink_mask(page, hb)
        a, b3 = ink_box(mf), ink_box(mp)
        ok = (a is not None and b3 is not None
              and all(abs(p - q) <= 4 for p, q in zip(a, b3)))
        check(f"the heart {song} fills the film's heart box", ok, (a, b3))
        # extents alone would pass a box-sized blob: the shape itself has to be
        # the film's heart (measured 0.91-0.92 here; a letterboxed or rounded
        # heart falls below 0.88, and its area falls short of the film's)
        iou = (mf & mp).sum() / max(1, (mf | mp).sum())
        area = mp.sum() / max(1, mf.sum())
        check(f"the heart {song} has the film's shape",
              iou >= 0.88 and 0.85 <= area <= 1.15,
              (round(float(iou), 3), round(float(area), 3)))

    # every small control has to do something, and the like has to change the
    # heart itself - its fill - not paint a plate behind it
    fill = "() => getComputedStyle(document.querySelector('.heart-body')).fill"
    pg.mouse.move(5, 5)                      # leave the key so :hover is not read
    before = pg.evaluate(fill)
    pg.click("#btnHeart")
    pg.mouse.move(5, 5)
    pg.wait_for_timeout(250)
    after = pg.evaluate(fill)
    pressed = pg.evaluate("() => document.getElementById('btnHeart').getAttribute('aria-pressed')")
    check("the like fills the heart", before != after and pressed == "true",
          (before, after, pressed))
    check("the like is marked in the list", pg.evaluate(
        "() => document.querySelectorAll('#list li.liked').length >= 1"))
    check("the liked heart clears 3:1 on its backdrop", pg.evaluate("""() => {
      const t = window.TRACKS[window.__player.index];
      const L = (h) => {
        const v = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
          .map((c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)));
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
      };
      const a = L(t.heart), b = L(t.heartBg);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    }""") >= 3.0)
    pg.click("#btnHeart")
    pg.wait_for_timeout(250)
    check("and unliking empties it again", pg.evaluate(fill) == before)

    pg.click("#btnPlus")
    pg.wait_for_timeout(150)
    check("the plus saves the track", pg.evaluate(
        "() => document.getElementById('btnPlus').getAttribute('aria-pressed')") == "true")
    check("the plus marks the track in the list", pg.evaluate(
        "() => document.querySelectorAll('#list li.added').length >= 1"))

    pg.click("#dots")
    pg.wait_for_timeout(200)
    check("the dots key shows the song's info", pg.evaluate("""() => {
      const p = document.getElementById('info');
      return !p.hidden && document.getElementById('infoTitle').textContent.length > 0
        && document.getElementById('dots').getAttribute('aria-expanded') === 'true';
    }"""))
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(400)
    check("the open info follows the track", pg.evaluate("""() => {
      const t = window.TRACKS[window.__player.index];
      return !document.getElementById('info').hidden
        && document.getElementById('infoTitle').textContent === t.title;
    }"""))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    check("Escape closes it", pg.evaluate("() => document.getElementById('info').hidden"))

    pg.click("#chevron")
    pg.wait_for_timeout(250)
    opened = pg.evaluate("() => document.getElementById('sheet').classList.contains('open')")
    pg.click("#btnClose")
    pg.wait_for_timeout(250)
    closed = pg.evaluate("() => document.getElementById('sheet').classList.contains('open')")
    check("the chevron pulls the list down, close puts it back", opened and not closed)

    # a reload comes back to the song and the moment the listener left
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_function("window.__player && window.__player.audio.readyState >= 1")
    pg.evaluate("document.getElementById('phone').style.transform='scale(1)'")
    pg.evaluate("() => window.__player.load(4)")
    pg.wait_for_timeout(400)
    box = pg.query_selector("#bar").bounding_box()
    pg.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
    pg.wait_for_timeout(300)
    st = pg.evaluate("() => ({i: window.__player.index, t: window.__player.audio.currentTime})")
    pg.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_function(
        "() => window.__player && window.__player.audio.readyState >= 1"
        " && window.__player.audio.currentTime > 0", timeout=8000)
    back = pg.evaluate("() => ({i: window.__player.index, t: window.__player.audio.currentTime})")
    check("a reload resumes the song and the moment",
          back["i"] == st["i"] and abs(back["t"] - st["t"]) < 3, (st, back))
    pg.wait_for_timeout(1200)
    # resuming a position must not also start the sound: the listener opens the
    # page, the page waits for their play
    check("a resumed page stays silent until played",
          pg.evaluate("() => window.__player.audio.paused"))

    # a restore seek belongs to one load only: the next load must cancel it,
    # or the new track lands at the previous song's position
    pg.evaluate("() => { const p = window.__player; p.load(0, {at: 60}); p.load(1); }")
    pg.wait_for_timeout(1500)
    st = pg.evaluate("() => ({i: window.__player.index, t: window.__player.audio.currentTime})")
    check("a later load cancels the previous restore seek", st["i"] == 1 and st["t"] < 5, st)

    # A saved shape the player did not write must not stop the page loading.
    # The seed has to be in place before the document's own script runs: writing
    # it from the previous page is undone by that page's pagehide -> persist(),
    # and a same-tab write-then-reload is undone the same way.  So a fresh page
    # with an init script, which runs first.
    p2 = b.new_page(viewport={"width": 1080, "height": 1600})
    p2.add_init_script(
        "try{localStorage.setItem(\"warma.player\", '{\"liked\":3,\"added\":\"x\"}')}"
        "catch(e){}")
    p2.goto(URL + "?t=0", wait_until="domcontentloaded")
    p2.wait_for_function("window.__player !== undefined", timeout=5000)
    check("a malformed saved state does not take the player down",
          p2.evaluate("() => !!window.__player && window.__player.index >= 0"))
    p2.evaluate("() => localStorage.removeItem('warma.player')")
    p2.close()

    # a returning visitor: the saved song and moment come back, and the page
    # does not start making sound on its own
    p3 = b.new_page(viewport={"width": 1080, "height": 1600})
    p3.add_init_script(
        "try{localStorage.setItem(\"warma.player\","
        " '{\"liked\":[],\"added\":[],\"index\":3,\"time\":40}')}catch(e){}")
    p3.goto(URL, wait_until="domcontentloaded")
    p3.wait_for_function("window.__player && window.__player.audio.readyState >= 1"
                         " && window.__player.audio.currentTime > 0", timeout=8000)
    p3.wait_for_timeout(1500)
    st = p3.evaluate("() => ({i: window.__player.index, t: window.__player.audio.currentTime,"
                     " paused: window.__player.audio.paused})")
    check("a returning visitor resumes paused", st["i"] == 3 and st["paused"], st)
    p3.close()

    check("no console errors", not errors, errors[:3])

    # In its own context, because this page's service worker serves audio from
    # its cache: the requests would never reach the network, the route would
    # never see them, and the tracks would play from cache (verified - the first
    # version of this check read 0 requests and a playing page).
    # service work: blocked, so no worker can serve the audio from its cache and
    # take the request out of the route's view
    ctx2 = b.new_context(service_workers="block")
    tries = []
    ctx2.route("**/assets/audio/*",
               lambda route: (tries.append(route.request.url), route.abort()))
    pg2 = ctx2.new_page()
    pg2.goto(URL + "?t=0", wait_until="domcontentloaded")
    pg2.wait_for_function("window.__player !== undefined", timeout=5000)
    pg2.evaluate("() => window.__player.play()")
    pg2.wait_for_timeout(4000)
    st = pg2.evaluate("() => ({paused: window.__player.audio.paused, i: window.__player.index})")
    check("a dead audio folder stops after one turn",
          st["paused"] and 0 < len(tries) <= 16, (st, len(tries)))
    ctx2.close()

    b.close()

print()
print("FAILED:", fails if fails else "none")
sys.exit(1 if fails else 0)
