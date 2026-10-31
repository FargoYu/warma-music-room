# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A working 12-track music player that recreates the player UI from Bilibili video
`BV1q1nH6CEbR`. Fidelity to the footage is the requirement: every position, colour
and size is **measured off the film** and stored in `_frames/*.json`, never designed
by hand. When something looks "off", the fix is almost always a measurement, not a
stylistic choice.

## Commands

All tools use repo-relative paths: **run everything from the repo root**. The page
is static; every browser check needs the server up.

```bash
python tools/serve.py                 # http://127.0.0.1:8770/index.html (port optional)
python tools/build_stills.py          # cut the stills (all songs; optional: song numbers)
python tools/build_anim.py            # encode the per-song clips from the same erasers
python tools/build_data3.py           # regenerate web/js/data.js from the measurements
```

The build order matters: stills, then anim, then data. `build_data3.py` stamps
every asset URL with the file's mtime *and* rewrites the `?v=` on the page's own
`css/js` links to the newest of data.js, player.js and player.css, so a rebuild
that skips it - or a hand edit to the page's code - leaves the browser (and the
service worker) holding the old picture under the new code.

Checks — each prints a per-song table (e2e prints a per-check list) and a final
`FAILED: ...` line, exiting non-zero on failure:

```bash
python tools/e2e.py          # interactions, freeze-on-pause, drawing actually changes,
                             # the play/pause glyphs' pixels
python tools/data_check.py   # data.js == what build_data3 computes == what the page
                             # paints with, and the contrast floors on those colours
python tools/knob_check.py   # live knob vs the film's knob position (<= 1.5 px), its
                             # height on the bar, and that its mask paints a sprite
python tools/clock_check.py  # live clock slots, baseline, cap height, glyph identity,
                             # its value on the film's axis via timeupdate, that its
                             # cells paint strokes and not blocks, and the colour floors
python tools/qa_stills.py    # erasure residue, play/heart actually erased (mean and
                             # the residual share), page-vs-still fidelity, clip moves
python tools/qa_frames.py    # every clip carries all its frames at 30 fps; a wrap
                             # that is a cut fails unless it is the recorded one
python tools/qa_perframe.py  # every frame against the film frame it came from
python tools/qa_erase.py     # knob and clock gone from every frame, rebuilt patches steady
                             # (the knob is measured as each frame draws it, not
                             # only inside the eraser's own silhouette)
python tools/qa_live.py      # the page on frame k against the clip's own frame k
python tools/qa_play.py      # a song actually plays: the picture keeps moving
```

There is no build step, linter or test runner; these ten scripts are the whole
suite. `python tools/e2e.py` alone is the single-test equivalent.

## Architecture

Two layers stacked in `web/index.html`:

**Art layer** (`#pics`) — per song, one still cut from the footage
(`web/assets/pic/NN_0.png`) plus the film's own motion as a whole-frame clip
(`web/assets/anim/NN.webm`, VP9 4:4:4 full range). The
whole picture moves in the film (posters pulse, clouds sweep, linework boils),
so the clip is the entire frame, not a crop: a crop seams wherever content
crosses its edge and freezes everything outside it. The clip is fetched only
when a song is first played; when the audio stops the clip is paused and left on
screen, so a paused song freezes on the drawing it had reached instead of
jumping back to the first. The still underneath is the clip's own first frame,
so it carries the picture until the clip has been fetched, and for a song that
has never been played.

The knob, the elapsed clock, the play key and the heart are erased from the
still; the still's transport row (bar, total time, prev/next) keeps the film's
shapes and its ink, except where that ink would fall under 2:1 on the backdrop
actually behind it - the vanishing point, not a legibility target. The poster's
flat base colour is not that backdrop (it reports ~1.5:1 for controls sitting on
a brighter part of the drawing), so the decision is made per box from
`local_bg`; prev and next are one control drawn twice and always share a colour.
On the twelve songs here the floor is never reached, so every painted control
keeps the film's own ink; the correction is a safety net, not a restyle.

**Live layer** (`#ui`) — draws the scrub knob (per-song sprite + measured ink,
riding the film's own track), the elapsed clock (the film's handwriting lifted into
a glyph atlas at `web/assets/ui/clock.png`, on four measured slots, baseline and cap
height), the play/pause key (the film never shows a pause state, and its painted
triangle is erased from the still) and the heart. The film paints the heart in two
tones - a rim in the song's ink, a body in the song's heart colour - and never
shows a liked state, so the painted heart is erased and redrawn keeping the rim
and making the body the state: a pale tint when not liked, the film's own body
colour when liked - pushed along its grey axis only until it clears 3:1 on the
backdrop the erased heart sits on, because on five posters the film's body is
1.2-2.4:1 against that backdrop and the like would be invisible. Both the tint
and the fill are measured against that backdrop (`heartBg`), not the poster's
base colour. A plate painted behind the icon is a different gesture and was
explicitly rejected. The knob sprite and the atlas bitmap are
stamped like every other asset: the service worker caches `/assets/ui/`
cache-first, so an unstamped sprite would be served stale forever. Their colours come from `data.js`: `live`
(≥3:1 against the poster) for the knob, `ctl` (≥2:1) for the clock and `play`
(≥3:1) for the key. The clock's floor is the still's own: the painted total-time
clock keeps the film's ink down to the vanishing point, and the elapsed clock has
to be the same colour, so `ctl` uses the same floor and the same kind of
reference. That is a deliberate fidelity trade-off - 2:1 is below any text
contrast guideline - made because the film's own handwriting on these posters is
what the page is reproducing, and the floor exists to catch ink that has
vanished, not to restyle it. The key is the one control a listener must find, so
it keeps a higher floor. Both `ctl` and `play` are measured against the backdrop that
sits **under that box in the still**, not the poster's flat base colour — the
base colour reports 1.5:1 for a key lying on white at 13:1, and "fixing" that
paints the key out in a pale colour. The remaining icons and the bar line stay
painted in the still.

The page opts out of dark-mode extensions (`<meta name="darkreader-lock">`): the
player's colours are the film's measured values, and a browser extension that
remaps them makes every check's ground truth invisible to the viewer.

The eight measured boxes are real `<button>`s: the chevron and the list key open
the track sheet, the dots key shows the song's info (title, subtitle, and the
Bilibili video it was cut from), the heart toggles a like, the plus a save (its
state shows in the list - the poster has no drawn state for it), and
prev/play/next are the transport. Likes, saves, the song last played and its
position persist in `localStorage` (`warma.player`) and are restored on reload;
the `?t=` parameter, which every browser check uses, wins over the restored
track. The bar is an ARIA slider (`role="slider"` with a `m:ss / m:ss` value
text): with focus on it the arrows scrub ±5 s (Shift ±30 s) and Home/End go to
the ends, while the page-wide arrows skip tracks. Prev restarts a song that is
past 3 s and otherwise steps back a track, and any skip keeps the play/pause
state the listener chose.

`navigator.mediaSession` is wired to the same transport functions where the API
exists, so the lock screen, headset keys and the media notification drive this
player; none of it is visible on the page. An audio error steps to the next
track and gives up after a full turn instead of looping - the counter is cleared
by playback that actually advanced (`timeupdate`), never by `play`, which a dead
source fires before its own error.


`web/js/data.js` is generated output: palettes, bar/clock geometry, the knob
sprite, the still's URL and the clip's URL, per song. Edit `tools/build_data3.py`,
never `data.js`.

## Measurement data (`_frames/`, git-ignored)

Regenerating anything requires the extracted footage: `_frames/v/*.jpg` (1080x1894,
**1-based** numbering, 30 fps, one sequence covering all 12 songs end to end) plus the
measurement JSONs. `build_data3.py` reads `ui_geom`, `clock_left_final`,
`clock_layout`, `clock_ink`, `knob_final`, `stills`, `web/assets/ui/clock.json` and
`web/assets/audio/index.json`; `build_stills.py` reads `art_windows`,
`clock_left_final`, `clock_ink` and `ui_geom`.

- `art_windows.json` is the authority on which frame window each song was cut from.
  `loop_window.py` only *proposes* windows (writing `_frames/loop_plan.json`) so a
  re-run cannot silently invalidate existing artwork. `loop_seam.py` proposes the
  *length* of each window the same way (`art_windows_seam.json`): a length whose
  last frame differs from its first by more than an ordinary frame step is a cut,
  and the loop plays that cut as a flash of the whole picture every few seconds.
- The erasers live in `tools/build_art7.py` (`knob_silhouette`, `erase_knob`,
  `erase_clock`, `scrub_clock`, `erase_glyph` (the play key and the heart; the
  heart is handed both its inks, the rim's and the body's),
  `ring_backdrop`, `rebuild`, plus
  `local_bg`, the backdrop sampler the still's `recolor` measures its contrast
  against), imported by `build_stills.py`. The bar's rows are `build_art7.BAR`,
  shared by every tool and check that needs them - one table, so a typo cannot
  make a check disagree with the build.
- `tools/` holds ~158 files, mostly one-off measurement attempts from the
  measurement phase. Only the commands above are live.

## Gotchas

- The film's own knob position and its clock reading disagree with each other (it is
  a hand-drawn mock). The player drives both from `audio.currentTime`, with the clock
  mapped onto the film's printed total (`shown`), so the two are self-consistent;
  checks compare typography and geometry, not numeric agreement with the film.
- **The film's knob is painted once, but not in exactly one place.** Its measured
  centroid drifts 4-13 px across a song (hand-drawn jitter), so the eraser takes a
  majority silhouette over the whole song and widens it by that measured travel
  (`knob_silhouette`) - a silhouette without the travel leaves a visible crescent
  of knob on the frames at either end. Deciding per frame cannot work: whichever
  blob wins is a coin toss between the knob and the drawing behind it, so some
  frames keep the knob and others smear the drawing - and the clip plays the
  difference as a flicker.
- Everything the erasers rebuild is rebuilt **from the picture just outside the
  mask** (`rebuild`): the backdrop under a control is never shown in any frame, so
  there is nothing to inpaint from, and a median plate there is a median of control
  pixels. An inpaint leaves a smear on a flat poster and a solid blob where artwork
  runs under the shape. Across the bar the lines to blend along are the rows; behind
  the elapsed clock they are the columns, because the linework there runs
  near-vertically and a row-wise fill rubs it out.
- Where the ring around a box says the backdrop is flat (`ring_backdrop`), the box is
  laid down in that colour instead, and that is the only fill that leaves nothing
  behind: the stroke's soft outer rim survives any pass that only looks for ink and
  reads as a ghost of the digits. Measure the ring, not the box - the handwriting and
  its rim fill enough of a box to make a textured poster look flat and a flat poster
  look textured. The ring excludes the strip above the box: every control in the
  transport sits under the bar line.
- QA masks must cover the knob's overhang beyond **both** ends of the bar (the sprite
  is centred; ~60 px each side) *and* above and below it: the bar band is 8 px and
  the knob 23-41 px, so a mask that only clears the band rows reports the knob as
  the film's ink left in the still, and the live knob as a page defect. Both QA
  tests take the knob's box from `knob_silhouette` and from the page's own DOM.
- `qa_erase` measures the knob twice: over the song-wide silhouette the eraser
  uses, and over the knob *as that frame draws it*, found independently in the
  film frame. The second is what catches a silhouette that is too narrow for some
  frames; the first alone would pass its own idea of the knob - and it fails
  outright if no frame yields a knob candidate at all, since a loop that finds
  nothing reads as a perfect result.
- A storage seed written from an older page cannot test the page that follows:
  navigating away fires the old page's `pagehide` -> `persist()`, which
  overwrites the seed before the new document's script reads it. Seed with
  `add_init_script` on a fresh page instead (`e2e` does this for the malformed-
  state case).
- The live layer is checked in pixels as well as geometry. A knob whose mask
  failed to load still measures the right rect; a clock whose atlas cells lost
  their alpha still sits on the right slots. `knob_check` samples the sprite's
  own pixels (ink covers part of the box, never its corners) and `clock_check`
  measures each glyph cell's coverage, where a solid block reads 1.0 and a
  stroke 0.2-0.6; `e2e` samples the key's centre column, ink when paused (a
  triangle) and a gap when playing (two bars).
- `data_check` exists because every other check read colours from the builder
  and geometry from the page: editing `build_data3.py` without re-running it
  left them all green against a palette the page did not have. It compares
  `build_data3.tracks`, `window.TRACKS` and the computed colours.
- `qa_stills` asks the erased play/heart boxes two questions, a mean difference
  and the share of the film's ink that still matches within the threshold: a mean
  alone passes a half-erased glyph, because the half that changed scores high.
- A control that straddles two tones has no single corrected colour: song 10's
  prev/next sit half on a white cloud and half on violet, and lifting the film's
  dark ink for the violet makes the icons vanish on the white. That is why the
  still's correction floor is the vanishing point and not a 3:1 restyle - it was
  3:1 for one build and did exactly that.
- Colour helpers of the two build tools speak different orders and the
  conversion is silent: `build_art7.local_bg` and `build_stills._lum` take BGR
  (cv2's), while `build_data3.cleared_bg` hands out a hex string that
  `contrast`/`readable` parse as RGB. A channel swap there is invisible in the
  output - a contrast is still computed - but it measures against a colour that
  is not on screen: it accepted the clock on song 3 at 3.8:1 against a phantom
  6.3:1 and lifted song 7's prev/next for no reason.
- A clip loops: its last frame is followed by its first. If those two differ by
  more than an ordinary frame step the loop flashes the whole picture on every
  wrap, and no amount of correct erasing hides it. `qa_frames` measures the wrap
  on the clip as served and fails a cut. Eleven of the twelve songs join up.
  Song 10's scene never returns anywhere in its segment (the best window still
  wraps at 36 against a step of 12), and its forward loop's jump - measured 32 -
  was **chosen by the user** over a reversed (ping-pong) clip and over a
  cross-fade, both of which were built and rejected as worse. `qa_frames` holds
  that song to its recorded cut so it cannot get worse.
- A seek to a frame's *boundary* is a coin toss between that frame and the next
  one, so `qa_live.py` asks for the middle of the interval. The film's drawings
  differ frame to frame by far more than codec noise, and a page showing the
  neighbouring frame reads as thousands of mismatched pixels.
- `erase_clock` needs the per-song ink colour and a box grown ~4 px: the antialiased
  rim of the handwriting survives a tight box and reads as a grey smudge.
- **The clip must be VP9 `yuv444p -color_range pc`.** With the default yuv420
  and limited range, the browser's YUV->RGB lands about a level off the still
  (a visible rectangle) and 4:2:0 chroma re-adds block stripes. 4:4:4 full range
  measures 0.00 mean difference at frame 0.
- Known, accepted limits (from the five-round audit, not defects to rediscover):
  at 100% the live knob's lower overhang covers the left part of the printed
  total time (the film puts the time under the bar's end and its knob never
  travels; drawing the total clock live needs a measurement of its own); the
  knob's fill is `readable(INK, base)`, not `knob_final`'s measured fill, because
  the measured fill falls under 3:1 on the dark posters; the heart's resting body
  is a CSS tint rather than the film's body (the film never shows an unliked
  heart); the browser retains decoded media, so a pass over twelve songs holds
  ~1 GB until the tab is closed; each loop restart costs the decoder a 67-100 ms
  re-seek.
- Audio URLs are stamped like every other asset (`build_data3`): the service
  worker caches by URL, and an unstamped MP3 would be served stale after a
  re-trim. The worker caches images only (`pic`, `ui`) - media answers Range
  with 206 and `Cache.put` rejects partial responses.
- A media element fires `play` for a source that will then fail: order in
  Chromium is play, loadstart, error. Anything counting failures must be cleared
  by real progress, not by `play`.
- The source video is 4:2:0, so flat poster areas carry block structure; `dechroma`
  in `tools/build_stills.py` smooths chroma where the luma is flat and keeps it at
  luma edges, and stills are written as PNG (lossless) so nothing re-softens them.
- `prefers-reduced-motion` turns off the player's own animations (the heart and
  plus presses, the sheet's blur), not the clip: the artwork's cycle is the
  product here, not decoration, and a still player is a different product.  The
  decision is recorded in `player.css` beside the media query.
- The song-info popover and the list sheet are the two surfaces not measured off
  the film: the film has neither, so their colours and geometry are the only
  hand-designed values on the page. Everything else - the poster, the eight
  boxes, the bar, the clock, the knob - comes from `_frames/*.json`.
- The artwork stops at `ART_BOTTOM` (1600): below the transport row there is only
  background and the uploader's watermark, so that strip is cropped away rather
  than repaired. Changing it means rebuilding `web/assets/pic` and `web/assets/anim`
  and updating `--h` / `BASE_H`.
- Periods are frames / 30; the loop windows assume 30 fps.

## Testing discipline

The checks are load-bearing: mutating the code must make them fail. Verified
mutations that are caught: the knob eraser disabled (`qa_erase`: 0.00 of the
knob's footprint erased against the 0.35 floor), the clock eraser disabled
(`qa_erase`: the box differs from the film by 1.1-3.6 against a 5.0 floor), the
heart eraser disabled (`qa_stills`: the erased boxes still match the film within
2.7 levels against a floor of 12, and 100% of the glyph ink still matches
against a 10% ceiling - residue and page-vs-still both stay at 0, because the
live heart covers the box, so those two columns are the only place the hole
shows), the dead-audio counter reset moved back into the `play` handler (`e2e`:
479 audio requests and still playing after 4 s, against 12 requests and
paused), the film-total time mapping broken (`clock_check`: ten of twelve songs
read the audio's axis through `timeupdate`), the heart letterboxed in its own
box again (`e2e`: shape IoU 0.848 against a floor of 0.88 - the extent check
still passes, which is why the shape check exists), the clip shifted 3 px
(`qa_live`: 40683 mismatched pixels), the clip never shown while playing
(`qa_play`: 14 of 14 shots on one frame), a loop that does not join up
(`qa_frames`: a wrap measured at 32 against a 13 step fails unless it is the
recorded one), the knob's mask and vertical offset removed (`knob_check`: ink
1.0 of its box, corners included, dy 12-16 px), the clock atlas' masks removed
(`clock_check`: every cell solid, coverage 0.94-1.00 against a 0.92 ceiling),
`data.js` edited by hand (`data_check`: one `ctl` byte and the page paints it),
wrong clock slots, dropped knob-centroid offset.

No known gap: the last one - the audio-duration -> film-total-time mapping
(`shownTime`) exercised only through `preview()` - is closed. `clock_check` now
seeks (the `timeupdate` path), moves the preview text off the target first so
`renderClock`'s same-text guard cannot let a stale value pass, and requires the
clock to read the film's printed total. The same check enforces the documented
contrast floors for every ink the player draws.
