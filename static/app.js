// static/app.js
(() => {
  "use strict";

  // ==== 1) 설정 ====
  const config = {
    RPM_MAX: 8000,
    SPEED_MAX: 100,
    RPM_IDLE_VALUE: 700,
    RPM_REDZONE_NORM: 7000 / 8000,
    AXIS_MIN: -50,
    AXIS_MAX: 50,
    AXIS_DEADZONE: 5.0,
    AXIS_SLEW_UP_PER_S: 140,
    AXIS_SLEW_DOWN_PER_S: 140,
    SEND_INTERVAL_MS: 70,
    TOAST_DURATION_MS: 2200,
    GAUGE_ANGLE_RANGE: 240,
  };

  // ==== 2) DOM ====
  const DOM = {
    body: document.body,
    needleRpm: document.getElementById("needleRpm"),
    needleSpeed: document.getElementById("needleSpeed"),
    readoutRpm: document.getElementById("readoutRpm"),
    readoutSpeed: document.getElementById("readoutSpeed"),
    gearIndicator: document.getElementById("gearIndicator"),
    gearButtons: [...document.querySelectorAll(".gear-btn")],
    btnHead: document.getElementById("btnHead"),
    btnEngine: document.getElementById("btnEngine"),
    btnSport: document.getElementById("btnSport"),
    axisBarFill: document.getElementById("axisBarFill"),
    axisBarFillNeg: document.getElementById("axisBarFillNeg"),
    axisReadout: document.getElementById("axisReadout"),
    netLatency: document.getElementById("netLatency"),
    toast: document.getElementById("toast"),
    shiftInfo: document.getElementById("shiftInfo"),
    shiftState: document.getElementById("shiftState"),
    torqueCmd: document.getElementById("torqueCmd"),
  };

  // ==== 3) 상태 ====
  const state = {
    rpm_norm: 0,
    speed_pct: 0,
    gear: "P",
    virtual_gear: 1,
    head_on: false,
    engine_running: false,
    sport_mode_on: false,
    shift_fail: false,
    axis: 0,        // -50..+50
  };
  const keyState = {};
  const prev = { ...state };

  // ==== 4) WebSocket ====
  let ws, isConnected = false, reconnectDelay = 1000;
  const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      isConnected = true;
      reconnectDelay = 1000;
      console.log("WebSocket connected.");
    };

    ws.onclose = () => {
      isConnected = false;
      console.log(`WebSocket disconnected. Retrying in ${reconnectDelay}ms...`);
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);

        // RTT
        if (typeof msg.pong === "number") {
          updateNetworkLatency(performance.now() - msg.pong);
          return;
        }

        // 서버 상태 동기화
        if (typeof msg.virtual_rpm === "number") state.rpm_norm = msg.virtual_rpm;
        if (typeof msg.speed_pct === "number") state.speed_pct = msg.speed_pct;

        if (msg.gear) {
          state.gear = msg.gear;
          if (msg.virtual_gear) state.virtual_gear = msg.virtual_gear;
        }

        if (typeof msg.head_on === "boolean") state.head_on = msg.head_on;
        if (typeof msg.sport_mode_on === "boolean") state.sport_mode_on = msg.sport_mode_on;

        if (typeof msg.engine_running === "boolean" && state.engine_running !== msg.engine_running) {
          state.engine_running = msg.engine_running;
          setClusterPower(state.engine_running);
          if (state.engine_running) onEngineStart(); else onEngineStop();
          // 엔진 on 시 P단 동기화는 서버가 처리함.
        }

        state.shift_fail = !!msg.shift_fail;

        render();
      } catch (e) {
        console.error("Failed to parse server message:", e);
      }
    };
  }

  function send(data) {
    if (isConnected && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  // 주기적 ping
  setInterval(() => send({ ping: performance.now() }), 1000);

  // ==== 5) 입력 처리 ====

  // 버튼 리스너 (index.html 구조와 일치):contentReference[oaicite:2]{index=2}
  DOM.gearButtons.forEach(b => b.addEventListener("click", () => send({ gear: b.dataset.gear })));
  DOM.btnHead.addEventListener("click", () => send({ head_toggle: true }));
  DOM.btnSport.addEventListener("click", () => send({ sport_mode_toggle: true })); // 서버가 무시해도 무해
  DOM.btnEngine.addEventListener("click", () => send({ engine_toggle: true }));

  // 조향: 자동 복귀 제거 → A/D 누르는 동안 steer_delta 반복 전송
  const STEER_STEP_DEG = 3;
  const STEER_SEND_MS = 50;
  let steerTimer = null;

  function startSteer(sign) {
    if (steerTimer) return;
    steerTimer = setInterval(() => {
      // 엔진 켜졌을 때만 의미 있음 (서버에서 가드)
      send({ steer_delta: sign * STEER_STEP_DEG });
    }, STEER_SEND_MS);
  }
  function stopSteer() {
    if (steerTimer) {
      clearInterval(steerTimer);
      steerTimer = null;
    }
  }

  // 키보드
  window.addEventListener("keydown", (e) => {
    const key = e.key.toLowerCase();
    if (keyState[key]) return; // 키 반복 방지
    keyState[key] = true;

    // 단축키들 (index.html UI와 매칭):contentReference[oaicite:3]{index=3}
    if ("prnd".includes(key)) send({ gear: key.toUpperCase() });
    if (key === "h") DOM.btnHead.click();
    if (key === "e") DOM.btnEngine.click();
    if (key === "m") DOM.btnSport.click();

    // 축 입력 (W/S)
    if (key === "w") state.axis = Math.min(config.AXIS_MAX, state.axis + 5);
    if (key === "s") state.axis = Math.max(config.AXIS_MIN, state.axis - 5);

    // 조향 입력 (A/D): steer_delta 반복 송신 시작
    if (key === "a") startSteer(-1);
    if (key === "d") startSteer(+1);
  });

  window.addEventListener("keyup", (e) => {
    const key = e.key.toLowerCase();
    keyState[key] = false;

    // A/D 모두 떼면 조향 전송 중지 (자동 복귀 없음)
    if ((key === "a" || key === "d") && !keyState.a && !keyState.d) {
      stopSteer();
    }
  });

  // ==== 6) 메인 루프 (axis 전송 + 렌더) ====
  let lastTimestamp = 0;
  let lastSendTime = 0;

  function mainLoop(ts) {
    if (!lastTimestamp) lastTimestamp = ts;
    const dt = (ts - lastTimestamp) / 1000.0;
    lastTimestamp = ts;

    // W/S 길게 눌렀을 때 부드럽게 변화
    const slewUp = config.AXIS_SLEW_UP_PER_S * dt;
    const slewDown = config.AXIS_SLEW_DOWN_PER_S * dt;
    if (keyState.w && !keyState.s) state.axis = clamp(state.axis + slewUp, config.AXIS_MIN, config.AXIS_MAX);
    else if (keyState.s && !keyState.w) state.axis = clamp(state.axis - slewDown, config.AXIS_MIN, config.AXIS_MAX);

    // 주기 전송 (axis)
    if (ts - lastSendTime >= config.SEND_INTERVAL_MS) {
      send({ axis: Math.round(state.axis) });
      lastSendTime = ts;
    }

    render();
    requestAnimationFrame(mainLoop);
  }

  // ==== 7) 렌더링 ====
  let sweep = { active: false, start: 0, up: 700, down: 600 };

  function render() {
    if (sweep.active) {
      renderSweep();
      return;
    }

    if (prev.rpm_norm !== state.rpm_norm)
      updateGauge(DOM.needleRpm, DOM.readoutRpm, state.rpm_norm * config.RPM_MAX, config.RPM_MAX, "", state.rpm_norm >= config.RPM_REDZONE_NORM);

    if (prev.speed_pct !== state.speed_pct)
      updateGauge(DOM.needleSpeed, DOM.readoutSpeed, state.speed_pct, config.SPEED_MAX, "%");

    if (prev.gear !== state.gear || prev.virtual_gear !== state.virtual_gear)
      updateGear();

    if (prev.head_on !== state.head_on)
      DOM.btnHead.classList.toggle("on", state.head_on);

    if (prev.sport_mode_on !== state.sport_mode_on)
      updateSportMode();

    if (prev.axis !== state.axis)
      updateAxisBar();

    if (state.shift_fail) {
      DOM.gearIndicator.classList.add("error");
      setTimeout(() => DOM.gearIndicator.classList.remove("error"), 400);
      state.shift_fail = false;
    }

    Object.assign(prev, state);
  }

  // --- 렌더 헬퍼 ---
  const clamp = (v, min, max) => v < min ? min : (v > max ? max : v);
  const valueToAngle = (value, max) => (clamp(value, 0, max) / max) * config.GAUGE_ANGLE_RANGE - (config.GAUGE_ANGLE_RANGE / 2);

  function updateGauge(needle, readout, value, max, unit = "", isRedzone = false) {
    needle.style.transform = `translate(-50%, -100%) rotate(${valueToAngle(value, max)}deg)`;
    needle.classList.toggle("redzone", isRedzone);
    readout.textContent = Math.round(value) + unit;
  }

  function updateGear() {
    const displayGear = (state.gear === "D" && state.virtual_gear) ? state.virtual_gear.toString() : state.gear;
    DOM.gearIndicator.textContent = displayGear;

    DOM.gearButtons.forEach(el => el.classList.toggle("active", el.dataset.gear === state.gear));
  }

  function updateSportMode() {
    DOM.body.classList.toggle("sport-mode-active", state.sport_mode_on);
    DOM.btnSport.classList.toggle("on", state.sport_mode_on);
  }

  function updateAxisBar() {
    const range = config.AXIS_MAX - config.AXIS_DEADZONE;
    const posPct = state.axis > config.AXIS_DEADZONE ? (state.axis - config.AXIS_DEADZONE) / range * 100 : 0;
    const negPct = state.axis < -config.AXIS_DEADZONE ? (-state.axis - config.AXIS_DEADZONE) / range * 100 : 0;
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

  // --- 엔진/애니메이션 ---
  function setClusterPower(on) {
    DOM.body.classList.toggle("cluster-on", on);
    DOM.body.classList.toggle("cluster-off", !on);
  }

  function onEngineStart() {
    sweep.active = true;
    sweep.start = performance.now();
  }

  function onEngineStop() {
    sweep.active = false;
  }

  function renderSweep() {
    const elapsed = performance.now() - sweep.start;
    const { up, down } = sweep;
    const total = up + down;
    const ease = t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

    let rpm, speed;
    if (elapsed < up) {
      const k = ease(elapsed / up);
      rpm = k * config.RPM_MAX;
      speed = k * config.SPEED_MAX;
    } else {
      const k = ease((elapsed - up) / down);
      rpm = (1 - k) * config.RPM_MAX;
      speed = (1 - k) * config.SPEED_MAX;
    }

    updateGauge(DOM.needleRpm, DOM.readoutRpm, rpm, config.RPM_MAX, "", (rpm / config.RPM_MAX) >= config.RPM_REDZONE_NORM);
    updateGauge(DOM.needleSpeed, DOM.readoutSpeed, speed, config.SPEED_MAX, "%");

    if (elapsed >= total) {
      sweep.active = false;
      updateGauge(DOM.needleRpm, DOM.readoutRpm, config.RPM_IDLE_VALUE, config.RPM_MAX, "", (config.RPM_IDLE_VALUE / config.RPM_MAX) >= config.RPM_REDZONE_NORM);
      updateGauge(DOM.needleSpeed, DOM.readoutSpeed, 0, config.SPEED_MAX, "%");
    }
  }

  // --- 토스트 ---
  function showToast(msg) {
    const el = document.createElement("div");
    el.className = "toast-msg";
    el.textContent = msg;
    DOM.toast.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(-8px)"; }, config.TOAST_DURATION_MS - 400);
    setTimeout(() => { DOM.toast.removeChild(el); }, config.TOAST_DURATION_MS);
  }

  // ==== 8) 시작 ====
  document.addEventListener("DOMContentLoaded", () => {
    setClusterPower(false);
    connect();
    requestAnimationFrame(mainLoop);
  });
})();
