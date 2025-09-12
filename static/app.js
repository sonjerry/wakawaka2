// app.js
// 클라이언트 제어 로직 (조향은 서버 주도, 자동 복귀 없음)

let ws;
let latency = 0;
let keyState = {};
let state = {
  engine_running: false,
  gear: "P",
  axis: 0,              // -50..+50 (브레이크/악셀 입력)
  head_on: false,
  sport_mode_on: false,
};

const STEER_STEP_DEG = 3;   // 한번에 회전 변화량 (도)
const STEER_SEND_MS = 50;   // 조향 입력 전송 주기(ms)
let steerInterval = null;

function connectWS() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => console.log("WebSocket connected");
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);

    if (msg.pong !== undefined) {
      latency = Date.now() - msg.pong;
      document.getElementById("netLatency").innerText = `${latency} ms`;
    }
    if (msg.engine_running !== undefined) {
      state.engine_running = msg.engine_running;
      updateCluster();
    }
    if (msg.gear !== undefined) {
      state.gear = msg.gear;
      updateGearDisplay();
    }
    if (msg.head_on !== undefined) {
      state.head_on = msg.head_on;
      updateHeadlight();
    }
    if (msg.message) {
      console.log("SERVER:", msg.message);
    }
  };
  ws.onclose = () => {
    console.log("WebSocket disconnected, retrying...");
    setTimeout(connectWS, 2000);
  };
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

// ========== 조향 처리: A/D 키 누르면 주기적으로 steer_delta 전송 ==========
function startSteerLoop(sign) {
  if (steerInterval) return;
  steerInterval = setInterval(() => {
    send({ steer_delta: sign * STEER_STEP_DEG });
  }, STEER_SEND_MS);
}
function stopSteerLoop() {
  if (steerInterval) {
    clearInterval(steerInterval);
    steerInterval = null;
  }
}

// ========== 키보드 이벤트 ==========
window.addEventListener("keydown", (e) => {
  const key = e.key.toLowerCase();
  if (keyState[key]) return; // 이미 누른 상태면 무시
  keyState[key] = true;

  if (key === "w") state.axis = Math.min(50, state.axis + 5);
  if (key === "s") state.axis = Math.max(-50, state.axis - 5);
  if (key === "p" || key === "r" || key === "n" || key === "d") {
    send({ gear: key.toUpperCase() });
  }
  if (key === "h") send({ head_toggle: true });
  if (key === "e") send({ engine_toggle: true });
  if (key === "m") toggleSportMode();

  if (key === "a") startSteerLoop(-1);
  if (key === "d") startSteerLoop(+1);

  send({ axis: Math.round(state.axis) });
});

window.addEventListener("keyup", (e) => {
  const key = e.key.toLowerCase();
  keyState[key] = false;

  if (key === "a" || key === "d") {
    if (!keyState.a && !keyState.d) stopSteerLoop();
  }
});

// ========== UI 업데이트 함수 ==========
function updateCluster() {
  const cluster = document.getElementById("cluster");
  if (state.engine_running) {
    cluster.classList.add("cluster-on");
    cluster.classList.remove("cluster-off");
  } else {
    cluster.classList.add("cluster-off");
    cluster.classList.remove("cluster-on");
  }
}
function updateGearDisplay() {
  document.getElementById("gearDisplay").innerText = state.gear;
}
function updateHeadlight() {
  const btn = document.getElementById("headBtn");
  if (state.head_on) {
    btn.classList.add("on");
  } else {
    btn.classList.remove("on");
  }
}
function toggleSportMode() {
  state.sport_mode_on = !state.sport_mode_on;
  document.body.classList.toggle("sport-mode-active", state.sport_mode_on);
}

// ========== 네트워크 핑 ==========
setInterval(() => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    send({ ping: Date.now() });
  }
}, 1000);

// 초기 연결
connectWS();
