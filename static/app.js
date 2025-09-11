const startStreaming = async () => {
    const pc = new RTCPeerConnection();
    const videoElement = document.getElementById('remoteVideo');

    pc.ontrack = (event) => {
        if (event.streams[0]) videoElement.srcObject = event.streams[0];
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const response = await fetch('http://100.84.162.124:8080/offer', { // URL 수정
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sdp: offer.sdp, type: offer.type })
    });
    const answer = await response.json();
    await pc.setRemoteDescription(new RTCSessionDescription(answer));
};

startStreaming();