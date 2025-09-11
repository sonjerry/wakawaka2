(() => {
  const video = document.getElementById('v');
  if (!video) return;

  async function start() {
    const pc = new RTCPeerConnection({ iceServers: [] });
    pc.ontrack = (e) => {
      video.srcObject = e.streams[0];
    };

    const offer = await pc.createOffer({ offerToReceiveVideo: true });
    await pc.setLocalDescription(offer);

    const res = await fetch('/offer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sdp: offer.sdp, type: offer.type })
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


