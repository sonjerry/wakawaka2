// ===== 설정: 필요하면 수정 =====
let WHEP_URL = "http://localhost:8080/whep";
// ==============================

const $ = (s) => document.querySelector(s);
const startBtn = $("#startBtn");
const statusEl = $("#status");
const urlInput = $("#whepUrl");
const videoEl = $("#video");

let pc = null;
let whepResource = null; // (서버가 반환하는 Location 헤더용; 여기선 비사용)

function setStatus(t) { statusEl.textContent = t; }

function waitIceComplete(pc) {
  return new Promise((resolve) => {
    if (pc.iceGatheringState === "complete") return resolve();
    const onStateChange = () => {
      if (pc.iceGatheringState === "complete") {
        pc.removeEventListener("icegatheringstatechange", onStateChange);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", onStateChange);
    // 안전 타임아웃(비차단)
    setTimeout(() => {
      pc.removeEventListener("icegatheringstatechange", onStateChange);
      resolve();
    }, 2000);
  });
}

async function start() {
  try {
    if (pc) return;
    WHEP_URL = urlInput.value.trim() || WHEP_URL;

    setStatus("초기화…");

    pc = new RTCPeerConnection({
      // 로컬/LAN이면 STUN 없어도 OK. 필요시 아래 주석 해제
      // iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
    });

    // 원격 비디오를 수신만 (recvonly)
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.addEventListener("track", (ev) => {
      if (ev.track.kind === "video") {
        videoEl.srcObject = ev.streams[0];
      }
    });

    pc.addEventListener("connectionstatechange", () => {
      setStatus(`연결 상태: ${pc.connectionState}`);
    });

    // SDP Offer 생성
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // non-trickle: ICE 후보가 모일 때까지 잠깐 대기
    await waitIceComplete(pc);

    // WHEP 규격: application/sdp 로 POST
    const res = await fetch(WHEP_URL, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: pc.localDescription.sdp
    });

    if (!res.ok) {
      setStatus(`오류: ${res.status} ${res.statusText}`);
      return;
    }

    const answerSdp = await res.text();
    const loc = res.headers.get("Location");
    if (loc) whepResource = loc;

    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
    setStatus("스트리밍 수신 중");
  } catch (e) {
    console.error(e);
    setStatus("오류 발생 (콘솔 확인)");
  }
}

startBtn.addEventListener("click", start);
