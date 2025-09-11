(() => {
  const video = document.getElementById('v');
  if (!video) return;

  async function start() {
    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    pc.ontrack = (e) => { video.srcObject = e.streams[0]; };
    pc.addTransceiver('video', { direction: 'recvonly' });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // ICE 수집 완료 대기(최대 3초)
    await new Promise((resolve) => {
      if (pc.iceGatheringState === 'complete') return resolve();
      const onChange = () => {
        if (pc.iceGatheringState === 'complete') {
          pc.removeEventListener('icegatheringstatechange', onChange);
          resolve();
        }
      };
      pc.addEventListener('icegatheringstatechange', onChange);
      setTimeout(() => {
        pc.removeEventListener('icegatheringstatechange', onChange);
        resolve();
      }, 3000);
    });

    const res = await fetch('/offer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type })
    });
    const answer = await res.json();
    await pc.setRemoteDescription(answer);
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    start();
  } else {
    window.addEventListener('DOMContentLoaded', start);
  }
})();