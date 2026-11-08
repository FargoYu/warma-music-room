// Horizontal swipes follow the same direction as the moving portrait.
let swipeStart = null;
stage.addEventListener('touchstart', event => {
  if (event.touches.length !== 1 || event.target.closest('input')) { swipeStart = null; return; }
  swipeStart = {x: event.touches[0].clientX, y: event.touches[0].clientY};
}, {passive: true});
stage.addEventListener('touchend', event => {
  if (!swipeStart || !event.changedTouches.length) return;
  const dx = event.changedTouches[0].clientX - swipeStart.x;
  const dy = event.changedTouches[0].clientY - swipeStart.y;
  swipeStart = null;
  if (Math.abs(dx) >= 40 && Math.abs(dx) > Math.abs(dy) * 1.3) {
    event.preventDefault(); // A swipe starting on a button must not also activate it.
    select(index + (dx < 0 ? 1 : -1), !audio.paused);
  }
}, {passive: false});
stage.addEventListener('touchcancel', () => { swipeStart = null; }, {passive: true});

