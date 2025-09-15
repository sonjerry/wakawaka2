// static/app.js
// 최소 구현: 키/버튼 입력 → 서버 전송, 조향은 steer_delta(자동 복귀 없음), 불필요 코드 제거

(() => {
  "use strict";

  // ===== 설정 =====
  const AXIS_MIN = -50;
  const AXIS_MAX = 50;
  const AXIS_RATE_PER_S = 40;     // W/S 누르고 있을 때 초당 변화량
  const SEND_INTERVAL_MS = 70;     // axis 전송 주기
  const STEER_STEP_DEG = 3;        // 조향 변화량(도)
  const STEER_SEND_MS = 50;        // 조향 전송 주기

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
    dbgSteer: document.getElementById("dbgSteer"),
    dbgThrottle: document.getElementById("dbgThrottle"),
    needleRpm: document.getElementById("needleRpm"),
    readoutRpm: document.getElementById("readoutRpm"),
    needleSpeed: document.getElementById("needleSpeed"),
    readoutSpeed: document.getElementById("readoutSpeed"),
  };

  // ===== 상태 =====
  const state = {
    engine_running: false,
    gear: "P",
    head_on: false,
    axis: 0,            // -50..50
  };
  const keyState = { w: false, s: false, a: false, d: false };

  // ===== WebSocket =====
  let ws;
  let isConnected = false;
  let reconnectDelay = 1000;
  const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      isConnected = true;
      reconnectDelay = 1000;
    };

    ws.onclose = () => {
      isConnected = false;
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }

      if (typeof msg.pong === "number") {
        updateNetworkLatency(performance.now() - msg.pong);
        return;
      }
      if (typeof msg.engine_running === "boolean") {
        state.engine_running = msg.engine_running;
        setClusterPower(state.engine_running);
        updateGearUI();
      }
      if (typeof msg.head_on === "boolean") {
        state.head_on = msg.head_on;
        DOM.btnHead.classList.toggle("on", state.head_on);
      }
      if (typeof msg.gear === "string") {
        state.gear = msg.gear;
        updateGearUI();
      }
      if (typeof msg.steer_angle === "number") {
        DOM.dbgSteer && (DOM.dbgSteer.textContent = `${Math.round(msg.steer_angle)}°`);
      }
      if (typeof msg.throttle_angle === "number") {
        DOM.dbgThrottle && (DOM.dbgThrottle.textContent = `${Math.round(msg.throttle_angle)}°`);
      }
      if (typeof msg.rpm === "number") {
        updateRpm(msg.rpm);
      }
      if (typeof msg.speed === "number") {
        updateSpeed(msg.speed);
      }
    };
  }

  function send(data) {
    if (isConnected && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  // ping (RTT)
  setInterval(() => send({ ping: performance.now() }), 1000);

  // ===== 버튼 이벤트 =====
  DOM.gearButtons.forEach(b => b.addEventListener("click", () => {
    send({ gear: b.dataset.gear });
  }));

  DOM.btnHead.addEventListener("click", () => {
    send({ head_toggle: true });
  });

  DOM.btnEngine.addEventListener("click", () => {
    send({ engine_toggle: true });
  });

  // ===== 키보드 이벤트 =====
  window.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    if (k in keyState && keyState[k]) return; // 중복 입력 방지
    if (k in keyState) keyState[k] = true;

    // 키보드로 기어 변경 기능 제거 (충돌 방지)
    if (k === "h") DOM.btnHead.click();
    if (k === "e") DOM.btnEngine.click();
  });

  window.addEventListener("keyup", (e) => {
    const k = e.key.toLowerCase();
    if (k in keyState) keyState[k] = false;
  });

  // ===== 조향: A/D 누르는 동안 주기적으로 steer_delta 전송 (자동 복귀 없음) =====
  let steerTimer = null;
  function updateSteerLoop() {
    const wantSteer = keyState.a || keyState.d;
    if (wantSteer && !steerTimer) {
      steerTimer = setInterval(() => {
        const sign = keyState.a && !keyState.d ? -1 : (keyState.d && !keyState.a ? +1 : 0);
        if (sign !== 0) send({ steer_delta: sign * STEER_STEP_DEG });
      }, STEER_SEND_MS);
    } else if (!wantSteer && steerTimer) {
      clearInterval(steerTimer);
      steerTimer = null;
    }
  }

  // ===== axis 전송 루프 =====
  let lastAxisSend = 0;
  function mainLoop(ts) {
    // axis 변화 (W/S 누르고 있을 때만)
    const dt = 1 / 60; // 간단히 고정 step
    if (keyState.w && !keyState.s) {
      state.axis = clamp(state.axis + AXIS_RATE_PER_S * dt, AXIS_MIN, AXIS_MAX);
    } else if (keyState.s && !keyState.w) {
      state.axis = clamp(state.axis - AXIS_RATE_PER_S * dt, AXIS_MIN, AXIS_MAX);
    }

    // axis 주기 전송
    if (ts - lastAxisSend >= SEND_INTERVAL_MS) {
      send({ axis: Math.round(state.axis) });
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
    DOM.gearIndicator.textContent = state.engine_running ? state.gear : "";
    DOM.gearButtons.forEach(el => el.classList.toggle("active", state.engine_running && el.dataset.gear === state.gear));
  }

  function updateAxisBar() {
    const range = AXIS_MAX - 5; // deadzone 5와 유사 동작
    const posPct = state.axis > 5 ? (state.axis - 5) / range * 100 : 0;
    const negPct = state.axis < -5 ? (-state.axis - 5) / range * 100 : 0;
    DOM.axisBarFill.style.height = `${posPct}%`;
    DOM.axisBarFillNeg.style.height = `${negPct}%`;
    DOM.axisReadout.textContent = Math.round(state.axis);
  }

  function updateNetworkLatency(rtt) {
    let color = "#8aff8a";
    if (rtt >= 200) color = "#ff6b6b";
    else if (rtt >= 80) color = "#ffd866";
    DOM.netLatency.textContent = `${Math.round(rtt)} ms`;
    DOM.netLatency.style.color = color;
  }

  // ===== 게이지 업데이트 =====
  function updateRpm(rpm) {
    const MAX_RPM = 8000;
    const clamped = rpm < 0 ? 0 : (rpm > MAX_RPM ? MAX_RPM : rpm);
    const angle = (clamped / MAX_RPM) * 270; // 0..270deg 스윕 가정
    if (DOM.needleRpm) DOM.needleRpm.style.transform = `rotate(${angle}deg)`;
    if (DOM.readoutRpm) DOM.readoutRpm.textContent = Math.round(clamped);
  }

  function updateSpeed(speed) {
    const MAX_SPEED = 120; // 임의 스케일 (UI용)
    const abs = Math.abs(speed);
    const clamped = abs > MAX_SPEED ? MAX_SPEED : abs;
    const angle = (clamped / MAX_SPEED) * 270;
    if (DOM.needleSpeed) DOM.needleSpeed.style.transform = `rotate(${angle}deg)`;
    if (DOM.readoutSpeed) DOM.readoutSpeed.textContent = `${Math.round(abs)}%`;
  }

  // ===== 시작 =====
  document.addEventListener("DOMContentLoaded", () => {
    setClusterPower(false);
    updateGearUI();
    updateAxisBar();
    connect();
    requestAnimationFrame(mainLoop);
  });
})();