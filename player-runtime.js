// Shared lifecycle: no animation-frame polling while paused, buffered or hidden.
function createFrameScheduler(audio, render) {
  let frame = 0, waiting = false;
  function stop() { cancelAnimationFrame(frame); frame = 0; }
  function active() { return !audio.paused && !audio.ended && !audio.seeking && !waiting && !document.hidden; }
  function run() {
    frame = 0;
    if (document.hidden) return;
    render();
    if (active()) frame = requestAnimationFrame(run);
  }
  function refresh(event) {
    if (['waiting', 'emptied'].includes(event?.type)) waiting = true;
    if (['playing', 'pause', 'loadeddata'].includes(event?.type)) waiting = false;
    stop();
    if (!document.hidden) frame = requestAnimationFrame(run);
  }
  const events = ['playing', 'pause', 'ended', 'waiting', 'emptied', 'loadeddata', 'seeking', 'seeked', 'timeupdate', 'ratechange'];
  events.forEach(name => audio.addEventListener(name, refresh));
  document.addEventListener('visibilitychange', refresh);
  return { refresh, destroy() {
    stop();
    events.forEach(name => audio.removeEventListener(name, refresh));
    document.removeEventListener('visibilitychange', refresh);
  }};
}

function readFavorites() {
  try {
    const saved = JSON.parse(localStorage.getItem('warma-favorites') || '[]');
    return new Set(Array.isArray(saved) ? saved.filter(Number.isInteger) : []);
  } catch { return new Set(); }
}

// Resolve cropped sprites before setting src so unused full-canvas PNGs never load.
function sceneImageSource(scene, layer, position, count) {
  if ((scene === 8 || scene === 9) ? position === count - 1 : position === 0)
    return `assets/player-ui/${scene + 1}.png`;
  if (scene === 3 && layer.name === '麻花辫') return 'assets/fourth/braid.png';
  if (scene === 3 && layer.name === '头发') return 'assets/fourth/hair.png';
  if (scene === 7 && SCENE8_MOTION.sprites[layer.name]) return SCENE8_MOTION.sprites[layer.name].src;
  return layer.src;
}

// Hold only the two neighboring scenes decoded, limiting mobile memory use.
function createScenePreloader(tracks) {
  const cache = new Map();
  function sources(scene) {
    const layers = tracks[scene].layers;
    const urls = layers.flatMap((layer, position) => {
      if (scene === 1 && layer.name === 'Really' || scene === 2 && position > 0) return [];
      return [sceneImageSource(scene, layer, position, layers.length)];
    });
    if (scene === 1) urls.push('assets/really.png');
    if (scene === 2) urls.push(...['person','planet','star1','star2','star3'].map(name => `assets/third/${name}.png`));
    return [...new Set(urls)];
  }
  function prepare(scene) {
    if (cache.has(scene)) return cache.get(scene);
    const images = sources(scene).map(src => { const image = new Image(); image.decoding = 'async'; image.src = src; return image; });
    const entry = {images, ready: Promise.all(images.map(image => image.decode().catch(() => {})))};
    cache.set(scene, entry);
    return entry;
  }
  return {neighbors(scene) {
    const wanted = [(scene + 1) % tracks.length, (scene - 1 + tracks.length) % tracks.length];
    for (const key of cache.keys()) if (!wanted.includes(key)) cache.delete(key);
    wanted.forEach(prepare);
  }};
}
