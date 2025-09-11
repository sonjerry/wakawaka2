(() => {
  const img = document.getElementById('stream');
  if (!img) return;
  const STREAM_URL = '/stream.mjpg';
  function start() {
    img.src = STREAM_URL + '?t=' + Date.now();
  }
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    start();
  } else {
    window.addEventListener('DOMContentLoaded', start);
  }
})();


