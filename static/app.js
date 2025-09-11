const startBtn = document.getElementById("startBtn");
const statusEl = document.getElementById("status");
const videoEl = document.getElementById("remoteVideo");

let pc = null;

function setStatus(text) {
  statusEl.textContent = text;
}

async function startStream() {
  if (pc) return;
  setStatus("초기화 중...");

  // 최소 구성: 단방향 수신용 RTCPeerConnection
  pc = new RTCPeerConnection({
    // 같은 머신/랜에서라면 ICE 서버 없어도 충분
    // 필요시 stun 서버 추가 가능
    // iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
  });

  // 원격 트랙 수신
  pc.addEventListener("track", (evt) => {
    if (evt.track.kind === "video") {
      videoEl.srcObject = evt.streams[0];
    }
  });

  pc.addEventListener("connectionstatechange", () => {
    setStatus(`연결 상태: ${pc.connectionState}`);
  });

  // 송신할 로컬 트랙 없음 (단방향)
  const offer = await pc.createOffer({
    offerToReceiveAudio: false,
    offerToReceiveVideo: true
  });
  await pc.setLocalDescription(offer);

  // 서버에 SDP 전송
  const res = await fetch("/offer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sdp: pc.localDescription.sdp,
      type: pc.localDescription.type
    })
  });

  if (!res.ok) {
    setStatus("오류: 서버 응답 실패");
    return;
  }

  const answer = await res.json();
  await pc.setRemoteDescription(answer);

  setStatus("스트리밍 수신 중");
}

startBtn.addEventListener("click", startStream);
