// static/app.js
// 최소 구현: 키/버튼 입력 → 서버 전송, 조향은 steer_delta(자동 복귀 없음), 불필요 코드 제거

(() => {
  "use strict";

  // ===== 설정 =====
  const AXIS_MIN = -50;
  const AXIS_MAX = 50;
  const AXIS_RATE_PER_S = 15;     // W/S 누르고 있을 때 초당 변화량 (40 -> 15로 감소)
  const SEND_INTERVAL_MS = 70;     // axis 전송 주기
  const STEER_STEP_DEG = 3;        // 조향 변화량(도) - 더 빠른 조향을 위해 증가 (1 -> 3)
  const STEER_SEND_MS = 12;        // 조향 전송 주기 - 더 빠른 조향을 위해 감소 (17 -> 12)

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
    const range = AXIS_MAX - 5; // deadzone 5
    const posPct = state.axis > 5 ? (state.axis - 5) / range * 100 : 0;
    const negPct = state.axis < -5 ? (-state.axis - 5) / range * 100 : 0;
    DOM.axisBarFill.style.height = `${posPct}%`;
    DOM.axisBarFillNeg.style.height = `${negPct}%`;

    // 색상/광도 동적 변경: R(빨강), N(노랑), D(파랑) 영역
    // -50~-5: 빨강 계열, -5~5: 노랑, 5~50: 파랑
    let glow = 0;
    let colorTop = '';
    let colorBottom = '';
    const absAxis = Math.abs(state.axis);
    if (state.axis < -5) {
      const t = Math.min(1, (absAxis - 5) / 45); // -5..-50 → 0..1
      glow = 6 + t * 18;
      colorTop = `rgba(255, 100, 80, ${0.6 + 0.4 * t})`;
      colorBottom = `rgba(255, 50, 30, ${0.6 + 0.4 * t})`;
      DOM.axisBarFillNeg.style.background = `linear-gradient(${colorTop}, ${colorBottom})`;
      DOM.axisBarFillNeg.style.boxShadow = `0 0 ${glow}px rgba(255, 60, 40, ${0.5 + 0.4 * t})`;
      DOM.axisBarFill.style.boxShadow = 'none';
    } else if (state.axis > 5) {
      const t = Math.min(1, (absAxis - 5) / 45); // 5..50 → 0..1
      glow = 6 + t * 18;
      colorTop = `rgba(120, 200, 255, ${0.6 + 0.4 * t})`;
      colorBottom = `rgba(60, 160, 255, ${0.6 + 0.4 * t})`;
      DOM.axisBarFill.style.background = `linear-gradient(${colorTop}, ${colorBottom})`;
      DOM.axisBarFill.style.boxShadow = `0 0 ${glow}px rgba(60, 160, 255, ${0.5 + 0.4 * t})`;
      DOM.axisBarFillNeg.style.boxShadow = 'none';
    } else {
      // -5..5: 은은한 노랑 앰비언트
      const t = absAxis / 5; // 0..1
      glow = 4 + t * 8;
      const y1 = `rgba(255, 220, 100, ${0.45 + 0.45 * t})`;
      const y2 = `rgba(255, 200, 60, ${0.45 + 0.45 * t})`;
      // 중앙 영역이므로 양/음 모두 살짝 빛남
      DOM.axisBarFill.style.background = `linear-gradient(${y1}, ${y2})`;
      DOM.axisBarFillNeg.style.background = `linear-gradient(${y1}, ${y2})`;
      DOM.axisBarFill.style.boxShadow = `0 0 ${glow}px rgba(255, 210, 80, ${0.4 + 0.5 * t})`;
      DOM.axisBarFillNeg.style.boxShadow = `0 0 ${glow}px rgba(255, 210, 80, ${0.4 + 0.5 * t})`;
    }
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
  let currentRpm = 0;
  let targetRpm = 0;
  let rpmAnimationFrame = null;

  function updateRpm(rpm) {
    targetRpm = rpm;
    
    // 웰컴 세레모니 중이거나 큰 변화가 있을 때는 더 부드러운 애니메이션
    const rpmDiff = Math.abs(targetRpm - currentRpm);
    if (rpmDiff > 100) {
      // 큰 변화일 때 애니메이션 프레임 사용
      if (!rpmAnimationFrame) {
        animateRpm();
      }
    } else {
      // 작은 변화일 때는 즉시 적용
      currentRpm = targetRpm;
      updateRpmDisplay();
    }
  }

  function animateRpm() {
    const diff = targetRpm - currentRpm;
    const step = diff * 0.08; // 부드러운 보간
    
    if (Math.abs(diff) > 1) {
      currentRpm += step;
      updateRpmDisplay();
      rpmAnimationFrame = requestAnimationFrame(animateRpm);
    } else {
      currentRpm = targetRpm;
      updateRpmDisplay();
      rpmAnimationFrame = null;
    }
  }

  function updateRpmDisplay() {
    const MAX_RPM = 8000;
    const clamped = currentRpm < 0 ? 0 : (currentRpm > MAX_RPM ? MAX_RPM : currentRpm);
    const MIN_DEG = -135; // 0일 때 7시 방향
    const MAX_DEG = 135;  // 최대치일 때 5시 방향
    const angle = MIN_DEG + (clamped / MAX_RPM) * (MAX_DEG - MIN_DEG);
    if (DOM.needleRpm) DOM.needleRpm.style.transform = `translate(-50%, -100%) rotate(${angle}deg)`;
    if (DOM.readoutRpm) DOM.readoutRpm.textContent = Math.round(clamped);
  }

  function updateSpeed(speed) {
    const MAX_SPEED = 120; // 임의 스케일 (UI용)
    const abs = Math.abs(speed);
    const clamped = abs > MAX_SPEED ? MAX_SPEED : abs;
    const MIN_DEG = -135;
    const MAX_DEG = 135;
    const angle = MIN_DEG + (clamped / MAX_SPEED) * (MAX_DEG - MIN_DEG);
    if (DOM.needleSpeed) DOM.needleSpeed.style.transform = `translate(-50%, -100%) rotate(${angle}deg)`;
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