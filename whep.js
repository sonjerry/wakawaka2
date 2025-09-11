/* Minimal WHEP receiver (non-trickle ICE for simplicity/compatibility) */

function waitForIceGatheringComplete(peerConnection) {
  if (peerConnection.iceGatheringState === 'complete') return Promise.resolve();
  return new Promise((resolve) => {
    const check = () => {
      if (peerConnection.iceGatheringState === 'complete') {
        peerConnection.removeEventListener('icegatheringstatechange', check);
        resolve();
      }
    };
    peerConnection.addEventListener('icegatheringstatechange', check);
  });
}

async function startWhepSession({ url, videoEl }) {
  const peerConnection = new RTCPeerConnection({
    iceServers: [],
    bundlePolicy: 'max-bundle',
  });

  // Receive-only video
  peerConnection.addTransceiver('video', { direction: 'recvonly' });

  // Attach remote track to the video element
  peerConnection.addEventListener('track', (event) => {
    const [stream] = event.streams;
    if (stream) {
      videoEl.srcObject = stream;
    } else {
      // Fallback if streams array is empty
      const ms = new MediaStream([event.track]);
      videoEl.srcObject = ms;
    }
  });

  // Create full (non-trickle) offer
  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);
  await waitForIceGatheringComplete(peerConnection);

  const fullOffer = peerConnection.localDescription;

  // Send to WHEP endpoint
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/sdp',
      'Accept': 'application/sdp',
    },
    body: fullOffer.sdp,
    mode: 'cors',
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`WHEP POST 실패 (${resp.status}) ${text}`);
  }

  // Resource URL for optional teardown (DELETE)
  const resourceUrl = resp.headers.get('Location') || url;
  const answerSdp = await resp.text();

  const answer = { type: 'answer', sdp: answerSdp };
  await peerConnection.setRemoteDescription(answer);

  return {
    peerConnection,
    resourceUrl,
    stop: async () => {
      try {
        if (resourceUrl && resourceUrl !== url) {
          await fetch(resourceUrl, { method: 'DELETE' }).catch(() => {});
        }
      } catch (_) {}
      try { peerConnection.getSenders().forEach((s) => s.track && s.track.stop()); } catch (_) {}
      try { peerConnection.close(); } catch (_) {}
      if (videoEl.srcObject) {
        try { videoEl.srcObject.getTracks().forEach(t => t.stop()); } catch (_) {}
        videoEl.srcObject = null;
      }
    },
  };
}

function buildUI({ videoEl, urlInput, form, connectBtn, disconnectBtn, fullscreenBtn }) {
  let session = null;

  async function connect() {
    const url = urlInput.value.trim();
    if (!url) return;
    setBusy(true);
    try {
      session = await startWhepSession({ url, videoEl });
      setConnected(true);
    } catch (err) {
      alert(err?.message || String(err));
      setConnected(false);
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (session) {
      try { await session.stop(); } catch (_) {}
      session = null;
    }
    setConnected(false);
  }

  function setBusy(busy) {
    connectBtn.disabled = busy;
    disconnectBtn.disabled = busy || !session;
    fullscreenBtn.disabled = busy || !session;
    urlInput.disabled = busy || !!session;
  }

  function setConnected(connected) {
    connectBtn.disabled = connected;
    disconnectBtn.disabled = !connected;
    fullscreenBtn.disabled = !connected;
    urlInput.disabled = connected;
  }

  form.addEventListener('submit', (e) => { e.preventDefault(); connect(); });
  disconnectBtn.addEventListener('click', disconnect);
  fullscreenBtn.addEventListener('click', async () => {
    const el = videoEl;
    if (!document.fullscreenElement) {
      await el.requestFullscreen().catch(() => {});
    } else {
      await document.exitFullscreen().catch(() => {});
    }
  });

  return { connect, disconnect, urlInput };
}


