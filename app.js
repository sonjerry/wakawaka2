(() => {
  const img = document.getElementById('stream');
  const start = document.getElementById('start');
  const stop = document.getElementById('stop');
  if (!img || !start || !stop) return;

  const STREAM_URL = '/stream.mjpg';
  let running = false;

  function startStream() {
    if (running) return;
    img.src = STREAM_URL + '?t=' + Date.now();
    running = true;
  }

  function stopStream() {
    if (!running) return;
    img.src = '';
    running = false;
  }

  start.addEventListener('click', startStream);
  stop.addEventListener('click', stopStream);
})();


