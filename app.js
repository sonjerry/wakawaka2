const $ = (s) => document.querySelector(s);
const startBtn = $("#startBtn");
const statusEl = $("#status");
const videoEl = $("#video");

let pc = null;

function setStatus(t) { statusEl.textContent = t; }

function waitIceComplete(pc) {
  return new Promise((resolve) => {
    if (pc.iceGatheringState === "complete") return resolve();
    const on = () => {
      if (pc.iceGatheringState === "complete") {
        pc.removeEventListener("icegatheringstatechange", on);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", on);
    setTimeout(() => { pc.removeEventListener("icegatheringstatechange", on); resolve(); }, 1500);
  });
}

async function start() {
  try {
    if (pc) return;
    setStatus("초기화…");

    pc = new RTCPeerConnection();            // 로컬/TS 환경이면 STUN 불필요
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.addEventListener("track", (ev) => {
      if (ev.track.kind === "video") videoEl.srcObject = ev.streams[0];
    });
    pc.addEventListener("connectionstatechange", () => setStatus(`연결 상태: ${pc.connectionState}`));

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitIceComplete(pc);               // non-trickle

    const res = await fetch("/whep", {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: pc.localDescription.sdp,
    });

    if (!res.ok) {
      setStatus(`오류: ${res.status} ${res.statusText}`);
      return;
    }

    const answerSdp = await res.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
    setStatus("스트리밍 수신 중");
  } catch (e) {
    console.error(e);
    setStatus("오류 (콘솔 확인)");
  }
}

startBtn.addEventListener("click", start);
