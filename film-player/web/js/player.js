/* Warma player - playback logic.
   The art layer IS the film: one lossless still per song, and that same frame's
   motion as a VP9 loop of the whole frame.  Four things were removed from it -
   the scrub knob, the elapsed clock, the play key and the heart - and the live
   layer draws exactly those four, so every other pixel is what the film drew. */
(function () {
  "use strict";

  // the artwork is cropped below the transport row: that strip is only
  // background and the uploader's watermark
  const BASE_W = 1080, BASE_H = 1600;
  const TRACKS = window.TRACKS;
  const ATLAS = window.CLOCK_ATLAS;
  const $ = (id) => document.getElementById(id);

  const phone = $("phone");
  const bgEl = $("bg");
  const picsEl = $("pics");
  const basePic = $("pic0");
  const crop = $("crop");

  // ---------- the artwork's motion ----------
  // The film's drawings differ by local linework, so no transform or dissolve
  // can move between them - but the motion itself is in the footage.  For each
  // song the moving region is cut out of the film and looped in place over the
  // still, so the artwork moves exactly as it does there.  The clip is the
  // whole frame (the knob, clock, play key and heart are erased from it per
  // frame, exactly as from the still).  It is fetched only
  // when the song is first played (a few MB per song), and the still carries
  // the picture until then - the still is the clip's own first frame.
  let cropFor = null;
  function loadCrop() {
    crop.pause();
    crop.hidden = true;
    cropFor = null;              // a new song: fetch its clip on first play
    crop.removeAttribute("src");
  }

  function ensureCrop(t) {
    if (cropFor === t.id) return;
    crop.src = t.crop.src;
    cropFor = t.id;
  }

  const audio = $("audio");
  const bar = $("bar");
  const knob = $("knob");
  const clockCur = $("clockCur");
  const playBtn = $("btnPlay");
  const heartBtn = $("btnHeart");
  const plusBtn = $("btnPlus");
  const chevronBtn = $("chevron");
  const dotsBtn = $("dots");
  const info = $("info");
  const listEl = $("list");
  const sheet = $("sheet");

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let index = 0;
  let dragging = false;
  // what the listener did, remembered: a like and a saved track both have to
  // survive a reload, or the controls are decoration
  const STORE = "warma.player";
  let saved = { liked: [], added: [] };
  try {
    const raw = JSON.parse(localStorage.getItem(STORE) || "{}");
    if (raw && typeof raw === "object") saved = raw;
  } catch (e) {}
  // a stored shape this player did not write (a hand-edited key, an older
  // build) must not stop the page from loading
  const asSet = (v) => new Set(Array.isArray(v) ? v : []);
  const liked = asSet(saved.liked);
  const added = asSet(saved.added);
  function persist() {
    if (pendingAt > 0) return;      // a resume is still waiting for metadata
    try {
      localStorage.setItem(STORE, JSON.stringify(
        { liked: [...liked], added: [...added],
          index: index, time: audio.currentTime || 0 }));
    } catch (e) {}
  }
  // The song and the moment, remembered at the quiet points (a pause, the tab
  // going away) rather than on every timeupdate, which would rewrite storage
  // several times a second for a value only a reload ever reads.
  window.addEventListener("pagehide", persist);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) persist();
  });
  const ATLAS_IMG = window.CLOCK_ATLAS.img || "assets/ui/clock.png";

  function fit() {
    const s = Math.min(window.innerWidth / BASE_W, window.innerHeight / BASE_H) * 0.96;
    phone.style.transform = "scale(" + s + ")";
  }
  window.addEventListener("resize", fit);
  fit();

  function setBox(el, b) {
    el.style.left = b[0] + "px";
    el.style.top = b[1] + "px";
    el.style.width = (b[2] - b[0]) + "px";
    el.style.height = (b[3] - b[1]) + "px";
  }

  function applyTheme(t) {
    phone.style.setProperty("--ink", t.ink);
    phone.style.setProperty("--heart", t.heart);
    phone.style.setProperty("--heart-bg", t.heartBg || t.bg);
    phone.style.setProperty("--bg", t.bg);
    bgEl.style.background = t.bg;
  }

  const BTN = {
    chevron: "chevron", dots: "dots", list: "btnList", heart: "btnHeart",
    plus: "btnPlus", prev: "btnPrev", play: "btnPlay", next: "btnNext"
  };

  function layoutGlyphs(t) {
    // the play key's ink is measured against the backdrop that key actually
    // sits on in the still, not against the poster's flat base colour
    playBtn.style.color = t.play;
    for (const key of Object.keys(t.glyph)) {
      const btn = document.getElementById(BTN[key]);
      if (btn) setBox(btn, t.glyph[key]);
    }
    $("btnList").classList.toggle("flip", !!t.flip.list);
    playBtn.classList.toggle("flip", !!t.flip.play);  // the mirrored posters' key points left
  }

  function layoutBar(t) {
    const b = t.bar;
    bar.style.left = b[0] + "px";
    bar.style.top = b[1] + "px";
    bar.style.width = (b[2] - b[0]) + "px";
    bar.style.height = (b[3] - b[1]) + "px";
    barW = b[2] - b[0];
    const k = t.knob;
    // the knob's fill is measured off the footage, which is not always the same
    // colour as the icons around it
    knob.style.background = t.live;
    knob.style.width = k.w + "px";
    knob.style.height = k.h + "px";
    // the knob's ink centroid, not its bounding box, must ride the bar's centre
    knob.style.marginLeft = (-k.cx) + "px";
    knob.style.marginTop = (-k.cy) + "px";
    const img = 'url("' + k.src + '")';
    knob.style.webkitMaskImage = img;
    knob.style.maskImage = img;
    knob.style.webkitMaskSize = "100% 100%";
    knob.style.maskSize = "100% 100%";
    knob.style.webkitMaskRepeat = "no-repeat";
    knob.style.maskRepeat = "no-repeat";
  }

  // ---------- clock ----------
  // The ten numerals are the film's own handwriting, lifted into an atlas, and
  // the film draws them on four fixed slots.  So each glyph is placed at its
  // measured slot and scaled to the song's own cap height, which reproduces the
  // film's layout rather than approximating it with letter-spacing.
  const ATLAS_CAP = ATLAS.cap;      // the atlas was lifted at the film's native size
  const bitCache = {};
  function clockBit(ch) {
    if (bitCache[ch]) return bitCache[ch];
    const c = ATLAS.cells[ch];
    bitCache[ch] = {
      w: c.w, h: c.h, ax: c.x, ah: c.h,
      image: 'url("' + ATLAS_IMG + '")'
    };
    return bitCache[ch];
  }

  // The film's own total-time clock is the authority on how long the song is
  // (the audio file is a few seconds shorter), so the elapsed clock is scaled
  // onto that same axis and the two never disagree.
  function shownTime(secs, t) {
    if (!audio.duration) return secs;
    return secs / audio.duration * t.shown;
  }

  const clockSlots = [];          // one span per slot, built when the song loads
  function layoutClock(t) {
    // the clock is a full-bleed layer: its glyphs are placed in absolute page
    // coordinates, at the slots the film measured
    clockCur.style.left = "0px";
    clockCur.style.top = "0px";
    clockCur.style.height = BASE_H + "px";

    // The slots, the scale and the colour are the song's, so the spans are
    // built once here; rendering then only swaps the mask of the digits that
    // actually changed.  Rebuilding five masked elements every second is churn
    // the film does not ask for.
    const c = t.clock;
    const k = c.cap / ATLAS_CAP;
    clockCur.innerHTML = "";
    clockSlots.length = 0;
    for (let i = 0; i < c.slots.length; i++) {
      const span = document.createElement("span");
      span.className = "bit";
      span.style.width = (ATLAS.cells["0"].w * k) + "px";
      span.style.height = (ATLAS.cells["0"].h * k) + "px";
      span.style.left = c.slots[i] + "px";
      span.style.top = (c.bottom + 1 - ATLAS.cells["0"].h * k) + "px";
      span.style.background = t.ctl;
      clockCur.appendChild(span);
      clockSlots.push({el: span, ch: null});
    }
    clockCur.dataset.text = "";
  }

  function showDigit(slot, ch, k) {
    if (slot.ch === ch) return;
    slot.ch = ch;
    const b = clockBit(ch);
    const el = slot.el;
    el.style.width = b.w * k + "px";
    el.style.height = b.h * k + "px";
    el.style.top = (layoutBottom + 1 - b.h * k) + "px";
    el.style.webkitMaskImage = b.image;
    el.style.maskImage = b.image;
    // the mask is the atlas scaled by k, so its offset must scale too
    const pos = (-b.ax * k) + "px " + ((b.ah - ATLAS.h) * k) + "px";
    el.style.webkitMaskPosition = pos;
    el.style.maskPosition = pos;
    el.style.webkitMaskSize = (ATLAS.w * k) + "px " + (ATLAS.h * k) + "px";
    el.style.maskSize = (ATLAS.w * k) + "px " + (ATLAS.h * k) + "px";
  }

  let layoutBottom = 0, layoutK = 0;
  function renderClock(secs, t) {
    const total = Math.max(0, Math.floor(secs));
    const m = Math.floor(total / 60);
    const sec = total % 60;
    const text = m + ":" + (sec < 10 ? "0" : "") + sec;
    if (clockCur.dataset.text === text) return;
    clockCur.dataset.text = text;
    const k = t.clock.cap / ATLAS_CAP;
    if (k !== layoutK || t.clock.bottom !== layoutBottom) {
      layoutK = k;
      layoutBottom = t.clock.bottom;
      for (const s of clockSlots) s.ch = null;      // the scale moved: redraw all
    }
    for (let i = 0; i < clockSlots.length; i++) {
      showDigit(clockSlots[i], i < text.length ? text[i] : " ", k);
    }
  }

  // ---------- progress ----------
  // The bar's width is fixed for the song, so it is measured once when the song
  // is laid out.  Reading it per tick - or worse, per pointermove - forces the
  // whole 1080x1600 subtree to lay out again for a number that has not changed.
  let barW = 0;
  function knobX(frac) {
    return Math.max(0, Math.min(1, frac)) * barW;
  }

  function fmt(secs) {
    const v = Math.max(0, Math.floor(secs));
    return Math.floor(v / 60) + ":" + String(v % 60).padStart(2, "0");
  }

  // The bar is a slider in the film's own clothes: it carries the value the
  // screen reader reads, and the knob is its visible thumb.
  let ariaNow = "", ariaText = "";
  function updateBar(frac) {
    frac = Math.max(0, Math.min(1, frac));
    knob.style.transform = "translateX(" + knobX(frac) + "px)";
    const shown = TRACKS[index].shown;
    const now = String(Math.round(frac * 100));
    const text = fmt(frac * shown) + " / " + fmt(shown);
    if (now !== ariaNow) bar.setAttribute("aria-valuenow", ariaNow = now);
    if (text !== ariaText) bar.setAttribute("aria-valuetext", ariaText = text);
  }

  // One way to move the play position, whoever asked - the bar, the keyboard,
  // the lock screen.  Everything else reads currentTime back out of the audio.
  function seekTo(secs) {
    if (!audio.duration) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration, secs));
    updateBar(audio.currentTime / audio.duration);
    renderClock(shownTime(audio.currentTime, TRACKS[index]), TRACKS[index]);
  }

  // ---------- transport ----------
  function play() {
    audio.preload = "auto";         // the listener asked: fetch the whole file
    const p = audio.play();
    if (p && p.catch) p.catch(function () {});
  }
  function pause() {
    audio.pause();
  }

  let pendingAt = 0;               // where to seek once metadata arrives
  audio.addEventListener("loadedmetadata", function () {
    if (pendingAt > 0) {
      const t0 = pendingAt;
      pendingAt = 0;
      if (isFinite(audio.duration) && audio.duration > 0) {
        audio.currentTime = Math.min(t0, Math.max(0, audio.duration - 0.25));
      }
    }
  });

  function load(i, opts) {
    opts = opts || {};
    // a drag belongs to the song it started on: a track change must not leave
    // timeupdate gated on `dragging` (the live layer would freeze) or let the
    // release seek the new track to the old fraction
    dragging = false;
    barRect = null;
    lastSeek = 0;
    index = (i + TRACKS.length) % TRACKS.length;
    const t = TRACKS[index];
    applyTheme(t);
    layoutGlyphs(t);
    mediaMeta(t);
    layoutBar(t);
    layoutClock(t);
    // the still drawing, and the film's own motion over it, both held until
    // the song plays
    basePic.src = t.pics[0];
    loadCrop();
    audio.src = t.audio;
    audio.load();
    // a fresh load is paused until the play event says otherwise; the key's
    // name must match what it will do, not what the page was built with
    playBtn.setAttribute("aria-label", "播放");
    renderClock(0, t);
    updateBar(0);
    lastPos = 0;                    // a new song: position state is stale
    mediaState();
    // the position is only known once the new source reports its duration;
    // one permanent listener reads this, so a newer load simply replaces it
    pendingAt = opts.at > 0 ? opts.at : 0;
    if (!info.hidden) showInfo();
    showLiked();
    plusBtn.classList.toggle("on", added.has(t.id));
    plusBtn.setAttribute("aria-pressed", added.has(t.id) ? "true" : "false");
    markList();
    if (opts.autoplay !== false) play();
  }

  function showLiked() {
    const t = TRACKS[index];
    const on = liked.has(t.id);
    heartBtn.classList.toggle("on", on);
    heartBtn.setAttribute("aria-pressed", on ? "true" : "false");
    heartBtn.setAttribute("aria-label", on ? "取消喜欢" : "喜欢");
  }

  function showInfo() {
    const t = TRACKS[index];
    $("infoTitle").textContent = t.title;
    $("infoSub").textContent = t.sub + (t.bv ? " · " + t.bv : "");
    const a = $("infoLink");
    a.href = t.bv ? "https://www.bilibili.com/video/" + t.bv : "https://www.bilibili.com/video/BV1q1nH6CEbR";
  }

  function markList() {
    [].forEach.call(listEl.children, function (li, i) {
      const t = TRACKS[i];
      li.classList.toggle("active", i === index);
      li.classList.toggle("liked", liked.has(t.id));
      li.classList.toggle("added", added.has(t.id));
    });
  }

  playBtn.addEventListener("click", function () { audio.paused ? play() : pause(); });
  // The usual rule: once a song is under way, "previous" means "again"; before
  // that it steps back a track.  Skipping also keeps the play/pause state the
  // listener chose rather than starting a song they had paused.
  const PREV_RESTART = 3;
  function skip(d) { load(index + d, { autoplay: !audio.paused }); }
  function prev() {
    if (audio.currentTime > PREV_RESTART) seekTo(0);
    else skip(-1);
  }
  $("btnPrev").addEventListener("click", prev);
  $("btnNext").addEventListener("click", function () { skip(1); });
  // The film never shows a pause state and its own triangle was erased from the
  // artwork, so the live button is what draws the key - a triangle while paused,
  // the bars while playing - in the song's own measured ink.
  audio.addEventListener("play", function () {
    mediaState();
    playBtn.classList.add("playing");
    playBtn.setAttribute("aria-label", "暂停");
    // the drawing moves only while the song does
    picsEl.classList.add("live");
    ensureCrop(TRACKS[index]);
    crop.hidden = false;
    if (crop.paused) { const q = crop.play(); if (q && q.catch) q.catch(function () {}); }
  });
  // A paused song is a frozen picture, not a reset one: the clip stops on the
  // frame it had reached and stays on screen.  The still shows only until a
  // song's clip has been fetched, or for a song that was never played.
  audio.addEventListener("pause", function () {
    persist();
    mediaState();
    playBtn.classList.remove("playing");
    playBtn.setAttribute("aria-label", "播放");
    picsEl.classList.remove("live");
    crop.pause();
  });
  // The system's own transport gets the same actions as the page's, where the
  // API exists: the lock screen, headset keys and the media notification then
  // drive this player instead of a generic one.  Nothing visible changes.
  function mediaMeta(t) {
    if (!("mediaSession" in navigator) || !window.MediaMetadata) return;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: t.title, artist: t.sub, album: "沃玛の播放器",
        artwork: [{ src: t.pics[0], sizes: "1080x1600", type: "image/png" }]
      });
    } catch (e) {}
  }
  if ("mediaSession" in navigator) {
    const set = function (action, fn) {
      try { navigator.mediaSession.setActionHandler(action, fn); } catch (e) {}
    };
    set("play", function () { play(); });
    set("pause", function () { pause(); });
    set("previoustrack", prev);
    set("nexttrack", function () { skip(1); });
    set("seekbackward", function (d) { seekTo(audio.currentTime - ((d && d.seekOffset) || 10)); });
    set("seekforward", function (d) { seekTo(audio.currentTime + ((d && d.seekOffset) || 10)); });
    set("seekto", function (d) { if (d && d.seekTime != null) seekTo(d.seekTime); });
  }
  let lastPos = 0;
  function mediaState() {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.playbackState = audio.paused ? "paused" : "playing";
    if (!navigator.mediaSession.setPositionState || !audio.duration) return;
    const now = performance.now();
    if (now - lastPos < 900) return;         // the spec asks for about 1 Hz
    lastPos = now;
    try {
      navigator.mediaSession.setPositionState({
        duration: audio.duration,
        position: Math.min(audio.currentTime, audio.duration),
        playbackRate: audio.playbackRate
      });
    } catch (e) {}
  }

  // A dead audio URL is not a crash and not a silent freeze: step to the next
  // track, but never circle forever - after a full turn the player gives up
  // and stays paused where it is.
  let deadTracks = 0;
  audio.addEventListener("error", function () {
    deadTracks += 1;
    if (deadTracks >= TRACKS.length) { pause(); return; }
    load(index + 1, { autoplay: !audio.paused });
  });

  audio.addEventListener("ended", function () { load(index + 1); });

  audio.addEventListener("timeupdate", function () {
    // a frame that actually advanced is the only proof a track loaded: a dead
    // source fires play first and error after, so resetting on play made the
    // give-up guard unreachable and the player cycled all twelve forever
    if (audio.currentTime > 0) deadTracks = 0;
    mediaState();
    if (dragging || !audio.duration) return;
    const f = audio.currentTime / audio.duration;
    updateBar(f);
    renderClock(shownTime(audio.currentTime, TRACKS[index]), TRACKS[index]);
  });

  // Scrubbing moves the artwork on every event, but the audio only every
  // SEEK_MS: writing currentTime on every pointermove aborts the in-flight
  // range request and re-initialises the demuxer up to 120 times a second, and
  // the ear cannot tell the difference.
  const SEEK_MS = 90;
  let barRect = null, lastSeek = 0;
  function seekFromEvent(e, force) {
    if (!barRect) barRect = bar.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - barRect.left) / barRect.width));
    updateBar(frac);
    renderClock(frac * TRACKS[index].shown, TRACKS[index]);
    if (!audio.duration) return;
    const now = performance.now();
    if (force || now - lastSeek >= SEEK_MS) {
      lastSeek = now;
      audio.currentTime = frac * audio.duration;
    }
  }
  bar.addEventListener("pointerdown", function (e) {
    dragging = true;
    barRect = bar.getBoundingClientRect();
    bar.setPointerCapture(e.pointerId);
    lastSeek = 0;
    seekFromEvent(e, true);
  });
  bar.addEventListener("pointermove", function (e) { if (dragging) seekFromEvent(e); });
  bar.addEventListener("pointerup", function (e) {
    if (!dragging) return;          // a release over the bar after a press elsewhere
    dragging = false;
    barRect = null;
    seekFromEvent(e, true);
  });
  bar.addEventListener("pointercancel", function () { dragging = false; });

  // With the bar focused, the arrow keys scrub it and Home/End jump to the
  // ends; the page-wide arrows (track skip) must not also fire.
  bar.addEventListener("keydown", function (e) {
    const step = e.shiftKey ? 30 : 5;
    let t;
    if (e.key === "ArrowRight") t = audio.currentTime + step;
    else if (e.key === "ArrowLeft") t = audio.currentTime - step;
    else if (e.key === "Home") t = 0;
    else if (e.key === "End") t = audio.duration || 0;
    else return;
    e.preventDefault();
    e.stopPropagation();
    seekTo(t);
  });

  heartBtn.addEventListener("click", function () {
    const t = TRACKS[index];
    if (liked.has(t.id)) liked.delete(t.id); else liked.add(t.id);
    showLiked();
    markList();
    persist();
    if (!reduce) {
      heartBtn.animate(
        [{ transform: "scale(1)" }, { transform: "scale(1.25)" }, { transform: "scale(1)" }],
        { duration: 360, easing: "cubic-bezier(.22,.61,.36,1)" });
    }
  });

  plusBtn.addEventListener("click", function () {
    const t = TRACKS[index];
    if (added.has(t.id)) added.delete(t.id); else added.add(t.id);
    plusBtn.classList.toggle("on", added.has(t.id));
    plusBtn.setAttribute("aria-pressed", added.has(t.id) ? "true" : "false");
    markList();
    persist();
    if (reduce) return;
    plusBtn.animate(
      [{ transform: "rotate(0deg)" }, { transform: "rotate(90deg)" }, { transform: "rotate(0deg)" }],
      { duration: 560, easing: "cubic-bezier(.22,.61,.36,1)" });
  });

  TRACKS.forEach(function (t, i) {
    const li = document.createElement("li");
    li.innerHTML = '<span class="n">' + String(i + 1).padStart(2, "0") + "</span>" +
      '<span class="t">' + t.title + "</span>" +
      '<span class="s">' + t.sub + "</span>";
    li.addEventListener("click", function () { closeSheet(); load(i); });
    listEl.appendChild(li);
  });

  let sheetFrom = null;
  function openSheet(ev) {
    sheetFrom = (ev && ev.currentTarget) || chevronBtn;
    sheet.classList.add("open");
    info.hidden = true;
    dotsBtn.setAttribute("aria-expanded", "false");
    markList();
  }
  function closeSheet() { sheet.classList.remove("open"); }
  // The top-left chevron is the pull-down for the list (the list key at the
  // foot of the poster is the other way in); the dots key is the song's own
  // information, with the video it was cut from.
  chevronBtn.addEventListener("click", openSheet);
  dotsBtn.addEventListener("click", function () {
    const open = info.hidden;
    info.hidden = !open;
    dotsBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      showInfo();
      info.focus();
    }
  });
  $("btnList").addEventListener("click", openSheet);
  $("btnClose").addEventListener("click", closeSheet);
  sheet.addEventListener("click", function (e) { if (e.target === sheet) closeSheet(); });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      const wasInfo = !info.hidden;
      const wasSheet = sheet.classList.contains("open");
      closeSheet();
      info.hidden = true;
      dotsBtn.setAttribute("aria-expanded", "false");
      // focus goes back to whatever opened the thing that just closed
      if (wasInfo) dotsBtn.focus();
      else if (wasSheet) (sheetFrom || chevronBtn).focus();
      return;
    }
    if (e.key === " ") {
      // a focused button keeps its own Space/Enter behaviour; Space toggles
      // playback only when the page itself has focus
      if (document.activeElement && document.activeElement.tagName === "BUTTON") return;
      e.preventDefault();
      audio.paused ? play() : pause();
      return;
    }
    if (e.key === "ArrowRight") skip(1);
    if (e.key === "ArrowLeft") skip(-1);
    if (e.key === "ArrowUp") audio.volume = Math.min(1, audio.volume + .1);
    if (e.key === "ArrowDown") audio.volume = Math.max(0, audio.volume - .1);
  });

  const qs = new URLSearchParams(location.search);
  const asked = parseInt(qs.get("t"), 10);
  const was = Number.isInteger(saved.index) ? saved.index : 0;
  const startAt = Math.max(0, Math.min(TRACKS.length - 1,
    Number.isInteger(asked) ? asked : was));
  const resumeAt = (Number.isInteger(asked) || startAt !== was) ? 0 : (saved.time || 0);
  mediaMeta(TRACKS[startAt]);
  load(startAt, { autoplay: false, at: resumeAt });

  // Put the two live elements where the film would have them at a given fraction
  // of the song.  Used by the screenshot harness so a shot and the source frame
  // it is compared with show the same moment.
  function preview(frac) {
    const t = TRACKS[index];
    const f = Math.max(0, Math.min(1, frac));
    updateBar(f);
    renderClock(f * t.shown, t);
  }

  // the artwork is cached after the first visit; a rebuilt asset gets a new
  // stamped URL (see tools/build_data3.py), so a stale copy is never served
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  }

  window.__player = {
    get index() { return index; },
    load: load, play: play, pause: pause, preview: preview,
    get audio() { return audio; },
    get pics() { return picsEl; }
  };
})();
