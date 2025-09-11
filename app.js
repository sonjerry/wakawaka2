const $ = (s) => document.querySelector(s);
const startBtn = $("#startBtn");
const statusEl = $("#status");
const urlInput = $("#whepUrl");
const videoEl = $("#video");

let pc = null;
let sessionUrl = null; // (서버가 Location 헤더로 주는 세션 URL; 여기선 보관만)

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
    setTimeout(() => { // 안전 타임아웃(논-트리클)
      pc.removeEventListener("icegatheringstatechange", onStateChange);
      resolve();
    }, 1500);
  });
}

async function start() {
  try {
    if (pc) return;

    const WHEP_URL = (urlInput.value || "").trim();
    if (!WHEP_URL) {
      setStatus("WHEP URL을 입력하세요");
      return;
    }

    setStatus("초기화…");

    pc = new RTCPeerConnection({
      // Tailscale이면 대부분 STUN 없이도 OK
      // iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
    });

    pc.addTransceiver("video", { direction: "recvonly" });

    pc.addEventListener("track", (ev) => {
      if (ev.track.kind === "video") {
        videoEl.srcObject = ev.streams[0];
      }
    });

    pc.addEventListener("connectionstatechange", () => {
      setStatus(`연결 상태: ${pc.connectionState}`);
    });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitIceComplete(pc); // non-trickle

    const res = await fetch(WHEP_URL, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: pc.localDescription.sdp,
    });

    if (!res.ok) {
      setStatus(`오류: ${res.status} ${res.statusText}`);
      return;
    }

    const answerSdp = await res.text();
    sessionUrl = res.headers.get("Location"); // 필요 시 종료/재협상에 사용

    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
    setStatus("스트리밍 수신 중");
  } catch (err) {
    console.error(err);
    setStatus("오류 발생 (콘솔 확인)");
  }
}

startBtn.addEventListener("click", start);
