(() => {
  const video = document.getElementById('v');
  if (!video) return;

  async function start() {
    console.log('[webrtc] init');
    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    pc.ontrack = (e) => {
      console.log('[webrtc] ontrack', e.streams[0]);
      video.srcObject = e.streams[0];
      video.muted = true;
      video.autoplay = true;
      video.playsInline = true;
      const p = video.play();
      if (p && typeof p.catch === 'function') p.catch(err => console.error('[webrtc] video.play error', err));
    };
    pc.onicegatheringstatechange = () => console.log('[webrtc] iceGatheringState', pc.iceGatheringState);
    pc.oniceconnectionstatechange = () => console.log('[webrtc] iceConnectionState', pc.iceConnectionState);
    pc.onconnectionstatechange = () => console.log('[webrtc] connectionState', pc.connectionState);
    pc.onicecandidateerror = (e) => console.warn('[webrtc] icecandidateerror', e);

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

    let answer;
    try {
      const res = await fetch('/offer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type })
      });
      const text = await res.text();
      try {
        answer = JSON.parse(text);
      } catch (e) {
        console.error('[webrtc] /offer non-JSON response:', text);
        throw e;
      }
    } catch (err) {
      console.error('[webrtc] /offer fetch error', err);
      return;
    }

    console.log('[webrtc] got answer');
    await pc.setRemoteDescription(answer);
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    start();
  } else {
    window.addEventListener('DOMContentLoaded', start);
  }
})();