// static/app.js
(() => {
  "use strict";

  // ===== 설정 =====
  const AXIS_MIN = -50;
  const AXIS_MAX = 50;
  const AXIS_RATE_PER_S = 140;
  const SEND_INTERVAL_MS = 70;
  const STEER_STEP_DEG = 3;
  const STEER_SEND_MS = 50;

  // ===== DOM =====
  const DOM = {
    body: document.body,
    gearIndicator: document.getElementById("gearIndicator"),
    gearButtons: [...document.querySelectorAll(".gear-btn")],
    btnHead: document.getElementById("btnHead"),
    btnEngine: document.getElementById("btnEngine"),
    axisBarFill: document.getElementById("axisBarFill"),
    axisBarFillNeg: document.getElementById("axisBarFillNeg"),
    axisReadout: document.getElementById("axisReadout"),
    netLatency: document.getElementById("netLatency"),
    rpmReadout: document.getElementById("readoutRpm"),
    speedReadout: document.getElementById("readoutSpeed"),
    needleRpm: document.getElementById("needleRpm"),
    needleSpeed: document.getElementById("needleSpeed"),
  };

  // ===== 상태 =====
  const state = {
    engine_running: false,
    gear: "P",
    head_on: false,
    axis: 0,
    steer_angle: 0,
    rpm: 0,
    speed: 0,
  };
  const keyState = { w: false, s: false, a: false, d: false };

  // ===== WebSocket =====
  const socket = io(window.location.origin, { transports: ["websocket", "polling"] });

  socket.on('update', (msg) => {
    if (typeof msg.engine_running === "boolean") {
      state.engine_running = msg.engine_running;
      setClusterPower(state.engine_running);
    }
    if (typeof msg.head_on === "boolean") {
      state.head_on = msg.head_on;
      DOM.btnHead.classList.toggle("on", state.head_on);
    }
    if (typeof msg.gear === "string") {
      state.gear = msg.gear;
      updateGearUI();
    }  
    if (typeof msg.axis === "number") {
      state.axis = msg.axis;
      updateAxisBar();
    }
    if (typeof msg.rpm === "number") {
      state.rpm = msg.rpm;
      updateGauge(DOM.needleRpm, DOM.rpmReadout, state.rpm, 8000);
    }
    if (typeof msg.speed === "number") {
      state.speed = msg.speed;
      updateGauge(DOM.needleSpeed, DOM.speedReadout, Math.abs(state.speed), 200);
      DOM.speedReadout.textContent = `${Math.round(Math.abs(state.speed))} km/h`;
    }
    if (typeof msg.steer_angle === "number") {
      state.steer_angle = msg.steer_angle;
    }
  });

  // ping (RTT)
  setInterval(() => socket.emit('message', JSON.stringify({ ping: performance.now() })), 1000);

  socket.on('pong', (msg) => {
    updateNetworkLatency(performance.now() - msg.pong);
  });

  // ===== 버튼 이벤트 =====
  DOM.gearButtons.forEach(b => b.addEventListener("click", () => {
    socket.emit('message', JSON.stringify({ gear: b.dataset.gear }));
  }));

  DOM.btnHead.addEventListener("click", () => {
    socket.emit('message', JSON.stringify({ head_toggle: true }));
  });

  DOM.btnEngine.addEventListener("click", () => {
    socket.emit('message', JSON.stringify({ engine_toggle: true }));
  });

  // ===== 키보드 이벤트 =====
  window.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    if (k in keyState && keyState[k]) return;
    if (k in keyState) keyState[k] = true;

    if ("prnd".includes(k)) socket.emit('message', JSON.stringify({ gear: k.toUpperCase() }));
    if (k === "h") DOM.btnHead.click();
    if (k === "e") DOM.btnEngine.click();
  });

  window.addEventListener("keyup", (e) => {
    const k = e.key.toLowerCase();
    if (k in keyState) keyState[k] = false;
  });

  // ===== 조향: A/D 누르는 동안 주기적으로 steer_delta 전송 =====
  let steerTimer = null;
  function updateSteerLoop() {
    const wantSteer = keyState.a || keyState.d;
    if (wantSteer && !steerTimer) {
      steerTimer = setInterval(() => {
        const sign = keyState.a && !keyState.d ? -1 : (keyState.d && !keyState.a ? +1 : 0);
        if (sign !== 0) socket.emit('message', JSON.stringify({ steer_delta: sign * STEER_STEP_DEG }));
      }, STEER_SEND_MS);
    } else if (!wantSteer && steerTimer) {
      clearInterval(steerTimer);
      steerTimer = null;
    }
  }

  // ===== axis 전송 루프 =====
  let lastAxisSend = 0;
  function mainLoop(ts) {
    const dt = 1 / 60;
    if (keyState.w && !keyState.s) {
      state.axis = clamp(state.axis + AXIS_RATE_PER_S * dt, AXIS_MIN, AXIS_MAX);
    } else if (keyState.s && !keyState.w) {
      state.axis = clamp(state.axis - AXIS_RATE_PER_S * dt, AXIS_MIN, AXIS_MAX);
    }

    if (ts - lastAxisSend >= SEND_INTERVAL_MS) {
      socket.emit('message', JSON.stringify({ axis: Math.round(state.axis) }));
      lastAxisSend = ts;
      updateAxisBar();
    }

    updateSteerLoop();
    requestAnimationFrame(mainLoop);
  }

  // ===== UI 헬퍼 =====
  function clamp(v, min, max) { return v < min ? min : (v > max ? max : v); }

  function setClusterPower(on) {
    DOM.body.classList.toggle("cluster-on", on);
    DOM.body.classList.toggle("cluster-off", !on);
  }

  function updateGearUI() {
    DOM.gearIndicator.textContent = state.gear;
    DOM.gearButtons.forEach(el => el.classList.toggle("active", el.dataset.gear === state.gear));
  }

  function updateAxisBar() {
    const range = AXIS_MAX - 5;
    const posPct = state.axis > 5 ? (state.axis - 5) / range * 100 : 0;
    const negPct = state.axis < -5 ? (-state.axis - 5) / range * 100 : 0;
    DOM.axisBarFill.style.height = `${posPct}%`;
    DOM.axisBarFillNeg.style.height = `${negPct}%`;
    DOM.axisReadout.textContent = Math.round(state.axis);
  }

  function updateGauge(needle, readout, value, max) {
    const angle = -120 + (value / max) * 240;
    needle.style.transform = `translate(-50%, -100%) rotate(${angle}deg)`;
    readout.textContent = Math.round(value);
  }

  function updateNetworkLatency(rtt) {
    let color = "#8aff8a";
    if (rtt >= 200) color = "#ff6b6b";
    else if (rtt >= 80) color = "#ffd866";
    DOM.netLatency.textContent = `${Math.round(rtt)} ms`;
    DOM.netLatency.style.color = color;
  }

  // ===== 시작 =====
  document.addEventListener("DOMContentLoaded", () => {
    setClusterPower(false);
    updateGearUI();
    updateAxisBar();
    requestAnimationFrame(mainLoop);
  });
})();