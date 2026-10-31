"""Emit web/js/data.js: everything the player needs, measured off the film.

The art layer is the footage itself (one lossless still per song, and that same
frame's motion as a VP9 loop) with only the things the player animates removed -
the scrub knob, the elapsed clock, the play key and the heart.  So every pixel
the player does not animate - the illustration, the background, the six other
control icons, the bar line, the total-time clock - is exactly what the film
drew.

What the live layer needs is therefore small: where the bar is, where the elapsed
clock sits and in what colour and size, the knob's silhouette, and where the
eight buttons are so they can be clicked.  All of it is measured per song by the
tools in this directory; nothing here is guessed.

The output is JSON (which is also valid JavaScript), so the data cannot be
mangled by string concatenation.
"""
import sys
sys.path.insert(0, "tools")
import json

from build_art7 import BAR, HEART   # shared with the eraser: one table each

INK = {1:"#9B6465",2:"#4D3838",3:"#FFFFFF",4:"#8A6661",5:"#51121E",6:"#FFFFFF",
       7:"#3E435D",8:"#9B6467",9:"#716096",10:"#1E0755",11:"#22184D",12:"#6C2F42"}
BG = {1:"#FFFFFF",2:"#55BDDC",3:"#FC5152",4:"#F8F4EA",5:"#F8F0E9",6:"#544D8E",
      7:"#221F29",8:"#FBFCF5",9:"#CFCCD1",10:"#342987",11:"#FB6E9A",12:"#FEFAF4"}
TITLES = [
    (1, "我家里有蜘蛛", "原创曲 · CB", "BV1ut411P7Sz"),
    (2, "I Really Like You", "翻唱", "BV1KE411D7dS"),
    (3, "惑星ループ", "行星环 · 翻唱", "BV1at411b7ac"),
    (4, "焦糖星", "中文人声本家", "BV1q441137TT"),
    (5, "甜蜜魔法", "生贺翻唱", "BV1ME411174q"),
    (6, "温软宇宙", "一只鸽子改变了一首歌的命运", "BV1XJ41157y8"),
    (7, "她追逐着月光的尽头", "翻唱", "BV1654y17773"),
    (8, "八珍玉食", "2024 拜年纪单品", "BV1W642137Gb"),
    (9, "泛泛人类不会祈祷", "人声本家", "BV1L34y1V7YP"),
    (10, "玛德琳娜电塔", "人声本家", "BV19J411Y788"),
    (11, "心跳叮叮咚", "原创曲", "BV1o4421Z7Mu"),
    (12, "夏天幻游日记", "来唱大家送我的歌", "BV18D4y1Y7o6"),
]
# the bar's own rows, measured once in build_art7 (it is the eraser's
# geometry too): one table, so a typo cannot make a check disagree with the build
SHOWN = {1:145, 2:136, 3:194, 4:236, 5:211, 6:239, 7:224,
         8:253, 9:259, 10:230, 11:210, 12:179}

GEOM = json.load(open("_frames/ui_geom.json"))
CLOCK = json.load(open("_frames/clock_left_final.json"))
CLAYOUT = json.load(open("_frames/clock_layout.json"))
CLOCK_INK = json.load(open("_frames/clock_ink.json"))
KNOB = json.load(open("_frames/knob_final.json"))
AUDIO = {t["id"]: t["duration"] for t in json.load(open("web/assets/audio/index.json"))}
STILLS = json.load(open("_frames/stills.json"))
CROPS = json.load(open("_frames/crops.json"))


def stamped(path):
    """Asset URL with a cache-buster, so a rebuilt clip is never served stale."""
    import os
    try:
        st = os.stat("web/" + path)
        return "%s?v=%d" % (path, int(st.st_mtime_ns // 1000000))
    except OSError:
        return path
ATLAS = json.load(open("web/assets/ui/clock.json"))


def _lum(h):
    h = h.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable(ink, bg, target):
    """The song's own ink, pushed toward black or white until it is legible.

    Two of the posters carry control ink that is almost the same value as the
    background (1.5:1); the artwork keeps its own colours, but the controls the
    player draws have to be visible, so the ink is moved along its own grey axis
    - the hue is kept - until it clears the target contrast.
    """
    if contrast(ink, bg) >= target:
        return ink
    h = ink.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    toward = 0 if _lum(bg) > 0.18 else 255
    best = ink
    for step in range(1, 101):
        f = step / 100
        c = "#%02X%02X%02X" % tuple(int(round(v + (toward - v) * f)) for v in (r, g, b))
        best = c
        if contrast(c, bg) >= target:
            break
    return best


def slots(s):
    """Button boxes, with the transport pair always prev-left / next-right.

    The mirrored half of the film is measured (ui_geom.json), not assumed: flip
    everything or nothing, whichever way the film actually drew it.
    """
    g = GEOM[str(s)]["box"]
    out = {k: list(v) for k, v in g.items()}
    a, b = out["prev"], out["next"]
    out["prev"], out["next"] = (a, b) if a[0] < b[0] else (b, a)
    m = GEOM[str(s)]["mirrored"]
    out["mirrored"] = {"list": m, "play": m}
    return out


_STILL_IMG = {}


def cleared_bg(i, box):
    """The colour the live glyph will sit on, straight out of the still.

    The erasers cleared that box, so the still's own pixels there are exactly the
    backdrop the player draws over - no guessing from the poster's base colour.
    The base colour is the wrong reference wherever artwork runs under a control:
    it reports 1.5:1 for a key that sits on white at 13:1, and "correcting" that
    paints the key out in a pale colour that is unreadable.
    """
    import cv2
    import numpy as np
    im = _STILL_IMG.get(i)
    if im is None:
        im = _STILL_IMG[i] = cv2.imread("web/assets/pic/%02d_0.png" % i)
    x0, y0, x1, y1 = box
    roi = im[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    b, g, r = np.median(roi, axis=0)     # cv2 hands back BGR
    return "#%02X%02X%02X" % (int(r), int(g), int(b))


tracks = []
for i, title, sub, bv in TITLES:
    g = slots(i)
    cl = CLOCK[str(i)]
    lay = CLAYOUT[str(i)]
    kn = KNOB[str(i)]
    hbg = cleared_bg(i, GEOM[str(i)]["box"]["heart"])
    tracks.append({
        "id": i, "title": title, "sub": sub, "bv": bv,
        "ink": INK[i], "bg": BG[i],
        # the heart's rim is the film's ink; the body is the film's own heart
        # colour, pushed along its grey axis only until it clears 3:1 on the
        # backdrop the erased heart sits on - on five posters the film's body is
        # within 1.2-2.4:1 of that backdrop and a like would be invisible
        "heart": readable(HEART[i], hbg, 3.0),
        "heartBg": hbg,
        # which half of the film is a mirror image: measured, not assumed -
        # the play key points the way the film's own key points
        "mirrored": g["mirrored"]["play"],
        # the still drawing, and the film's own moving region over it
        "pics": [stamped(p) for p in STILLS[str(i)]["pics"]],
        "crop": {
            # the clip is the whole frame; fetched on first play
            "src": stamped(CROPS[str(i)]["src"]),
        },
        # stamped like every other asset: the service worker caches by URL, and
        # an unstamped MP3 would be served stale after a re-trim
        "audio": stamped("assets/audio/%02d.mp3" % i),
        "shown": SHOWN[i],
        "bar": list(BAR[i]),
        # controls the player draws must stay legible on every poster
        # the clock and the key keep the film's own ink wherever it can be seen
        # at all: the painted total-time clock stays in that ink too, so the same
        # floor keeps the elapsed clock the same colour as it.  2:1 is the
        # vanishing point, not a legibility target - see build_stills.recolor.
        "ctl": readable(INK[i], cleared_bg(i, cl), 2.0),
        "play": readable(INK[i], cleared_bg(i, g["play"]), 3.0),
        "live": readable(INK[i], BG[i], 3.0),
        "clock": {
            "slots": lay["slots"],
            "bottom": lay["bottom"], "cap": lay["cap"],
        },
        "knob": {
            "w": kn["w"], "h": kn["h"], "cx": kn["cx"], "cy": kn["cy"],
            "src": stamped("assets/ui/knob_%02d.png" % i),
        },
        "glyph": {k: list(g[k]) for k in ("chevron", "dots", "list", "heart",
                                          "plus", "prev", "play", "next")},
        "flip": {"list": g["mirrored"]["list"], "play": g["mirrored"]["play"]},
    })

import re
def main():
    body = json.dumps(tracks, ensure_ascii=False, indent=1, separators=(",", ": "))
    # JSON pretty-printing breaks every number of an array onto its own line; the
    # coordinates read far better on one
    body = re.sub(r"\[\s*([-\d.,\s]+?)\s*\]", lambda m: "[" + ", ".join(
        x.strip() for x in m.group(1).split(",")) + "]", body)
    atlas = json.dumps(ATLAS, ensure_ascii=False, separators=(",", ": "))  # carries cap itself
    atlas_img = '"img": ' + json.dumps(stamped("assets/ui/clock.png")) + ","
    # the atlas bitmap is stamped next to the atlas json, so a re-cut image and
    # the cells that point into it move together
    out = (
        "/* 沃玛の播放器 —— 曲目元数据与逐首实测的界面几何。\n"
        "   由 tools/build_data3.py 从原片生成，不要手改。 */\n"
        "window.TRACKS = " + body + ";\n"
        "/* 时钟数字：原片里手写的十个字形，取成一张图集 */\n"
        "window.CLOCK_ATLAS = {" + atlas_img + atlas[1:] + ";\n"
    )
    open("web/js/data.js", "w", encoding="utf-8").write(out)
    # Stamp the page's own references with the same build, so a rebuilt data.js
    # can never be served from cache under yesterday's ?v=.  Hand-bumping this
    # was one step too many and silently served stale geometry.
    import os
    import re as _re
    # the page's own code moves too: stamp with the newest of the three, or an
    # edit to player.js would keep yesterday's ?v= and be served from cache
    v = max(int(os.stat(f).st_mtime_ns // 1000000) for f in
            ("web/js/data.js", "web/js/player.js", "web/css/player.css"))
    page = open("web/index.html", encoding="utf-8").read()
    page = _re.sub(r"(\?v=)\d+", lambda m: m.group(1) + str(v), page)
    open("web/index.html", "w", encoding="utf-8").write(page)
    print("tracks", len(tracks), "clock cells", list(ATLAS["cells"]))



if __name__ == "__main__":
    main()
