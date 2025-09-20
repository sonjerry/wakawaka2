// static/app.js
// 최소 구현: 키/버튼 입력 → 서버 전송, 조향은 steer_delta(자동 복귀 없음), 불필요 코드 제거

(() => {
  "use strict";

  // ===== 설정 =====
  const AXIS_MIN = -50;
  const AXIS_MAX = 50;
  const AXIS_RATE_PER_S = 15;     // W/S 누르고 있을 때 초당 변화량 (40 -> 15로 감소)
  const SEND_INTERVAL_MS = 70;     // axis 전송 주기
  const STEER_STEP_DEG = 2;        // 조향 변화량(도) - 더 빠른 조향을 위해 증가 (1 -> 3)
  const STEER_SEND_MS = 17;        // 조향 전송 주기 - 더 빠른 조향을 위해 감소 (17 -> 12)

  // ===== DOM =====
  const DOM = {
    body: document.body,
    videoStream: document.getElementById("videoStream"),
    videoFallback: document.getElementById("videoFallback"),
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
    speedValue: document.getElementById("speedValue"),
    carWheelFL: document.getElementById("carWheelFL"),
    carWheelFR: document.getElementById("carWheelFR"),
    carVisualWrapper: document.querySelector('.car-visual'),
  };

  // ===== 상태 =====
  const state = {
    engine_running: false,
    gear: "P",
    head_on: false,
    axis: 0,            // -50..50
    throttleAngle: 120, // ESC 중립 기준
    // 속도 표시용 상태 (부드러운 표시)
    targetSpeedKmh: 0,
    viewSpeedKmh: 0,
    // 조향/속도 시각화 상태
    targetSteerAngle: 0,
    visualSteerAngle: 0,
    lastSteerMsgAt: 0,
    displaySpeedKmh: 0,
  };
  const keyState = { w: false, s: false, a: false, d: false };

  // 웰컴 애니메이션 제거됨

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
        // 엔진 버튼 시각효과 토글
        if (DOM.btnEngine) {
          DOM.btnEngine.classList.toggle('on', state.engine_running);
        }
      }
      if (typeof msg.head_on === "boolean") {
        state.head_on = msg.head_on;
        DOM.btnHead.classList.toggle("on", state.head_on);
        updateHeadlightState();
      }
      if (typeof msg.gear === "string") {
        state.gear = msg.gear;
        updateGearUI();
        updateSpeedFromThrottle();
      }
      if (typeof msg.steer_angle === "number") {
        DOM.dbgSteer && (DOM.dbgSteer.textContent = `${Math.round(msg.steer_angle)}°`);
        state.targetSteerAngle = msg.steer_angle;
        state.lastSteerMsgAt = performance.now();
      }
      if (typeof msg.throttle_angle === "number") {
        state.throttleAngle = msg.throttle_angle;
        DOM.dbgThrottle && (DOM.dbgThrottle.textContent = `${Math.round(state.throttleAngle)}°`);
        updateSpeedFromThrottle();
      }
      // RPM 제거됨
      // 서버의 실제 속도 수신은 무시하고 (요구사항에 따라)
      // speed 게이지는 쓰로틀 출력 기반으로만 갱신
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

    // 속도 표시 스무딩 (즉각성과 부드러움 균형)
    {
      const TAU = 0.08; // 약 80ms 타임콘스턴트
      const alpha = 1 - Math.exp(-dt / TAU);
      const target = state.targetSpeedKmh;
      state.viewSpeedKmh += (target - state.viewSpeedKmh) * alpha;
      if (Math.abs(target - state.viewSpeedKmh) < 0.25) state.viewSpeedKmh = target;
      state.displaySpeedKmh = state.viewSpeedKmh;
      if (DOM.speedValue) DOM.speedValue.textContent = String(Math.round(state.viewSpeedKmh));
    }

    // 시각화용 조향 자동 정렬(쓰로틀에 비례해 빠르게 복귀)
    {
      const now = performance.now();
      const msSinceSteer = now - (state.lastSteerMsgAt || 0);
      let target = state.targetSteerAngle || 0;

      // 쓰로틀 기반 반환 속도 계산
      const t = Number(state.throttleAngle);
      let factor = 0; // 0..1
      const F_START = 130, F_END = 180; // 전진 구간
      const R_START = 120, R_END = 65;  // 후진 구간
      const R_DEAD = 2;                 // 후진 데드존(유휴 시 0 표시)
      if (state.gear === 'D') {
        factor = Math.max(0, Math.min(1, (t - F_START) / (F_END - F_START)));
      } else if (state.gear === 'R') {
        const effectiveStart = R_START - R_DEAD; // 118
        if (t < effectiveStart) {
          const clamped = Math.max(R_END, Math.min(effectiveStart, t));
          factor = (effectiveStart - clamped) / (effectiveStart - R_END);
        } else {
          factor = 0;
        }
      }

      if (msSinceSteer > 150 && factor > 0) {
        const returnRateDegPerSec = 10 + 70 * factor; // 쓰로틀↑ → 복귀 빠름
        const step = returnRateDegPerSec * dt;
        if (Math.abs(target) <= step) target = 0;
        else target += target > 0 ? -step : step;
        state.targetSteerAngle = target;
      }

      state.visualSteerAngle = target;
      updateCarSteer(state.visualSteerAngle);
    }

    updateSteerLoop();
    requestAnimationFrame(mainLoop);
  }

  // ===== UI 헬퍼 =====
  function clamp(v, min, max) { return v < min ? min : (v > max ? max : v); }

  function setClusterPower(on) {
    DOM.body.classList.toggle("cluster-on", on);
    DOM.body.classList.toggle("cluster-off", !on);
    const pill = document.getElementById("statusPill");
    if (pill) {
      pill.textContent = on ? "READY" : "OFF";
      pill.classList.toggle("on", on);
      pill.classList.toggle("off", !on);
    }
  }

  function updateCarSteer(angleDeg) {
    const clamped = Math.max(-35, Math.min(35, angleDeg));
    // 사용자 피드백에 따라 시각화 부호 보정: +각 → 시계방향 회전
    const visualDeg = clamped;
    if (DOM.carWheelFL) DOM.carWheelFL.style.transform = `rotate(${visualDeg}deg)`;
    if (DOM.carWheelFR) DOM.carWheelFR.style.transform = `rotate(${visualDeg}deg)`;
  }

  function updateHeadlightState() {
    if (!DOM.carVisualWrapper) return;
    DOM.carVisualWrapper.classList.toggle('headlight-on', !!state.head_on);
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

  // RPM 관련 로직 제거됨

  // ===== 쓰로틀 기반 Speed 숫자 표시 (Tesla 스타일) =====
  function updateSpeedFromThrottle() {
    // 요구사항: axis -5..5 근처에서 throttle ≈ 130
    // D: throttle 130 → 4 km/h, 180 → 60 km/h 선형 매핑
    // R: throttle 120 → 4 km/h, 65 → 60 km/h 선형 매핑, 유휴 데드존(118~130)은 0 km/h
    const t = Number(state.throttleAngle);
    let kmh = 0;

    if (state.gear === 'D') {
      if (t >= 130) {
        const tClamped = Math.min(180, t);
        kmh = 4 + (tClamped - 130) * (56 / 50); // 130..180 (50도) → 4..60
      } else {
        kmh = 0;
      }
    } else if (state.gear === 'R') {
      const DEAD = 2; // 120±2 내 유휴 처리
      if (t <= 120 - DEAD) {
        const tClamped = Math.max(65, t);
        kmh = 4 + ((120 - DEAD) - tClamped) * (56 / ((120 - DEAD) - 65));
      } else {
        kmh = 0;
      }
    } else {
      kmh = 0;
    }

    if (kmh < 0) kmh = 0;
    if (kmh > 60) kmh = 60;
    state.targetSpeedKmh = kmh;
  }

  // 웰컴 스윕 제거됨

  // ===== 시작 =====
  document.addEventListener("DOMContentLoaded", () => {
    initVideoFallback();
    setClusterPower(false);
    updateGearUI();
    updateAxisBar();
    updateHeadlightState();
    connect();
    requestAnimationFrame(mainLoop);
  });

  // (삭제됨) 눈금/숫자 생성 로직

  // ===== 영상 폴백: img 실패 시 iframe 표시 =====
  function initVideoFallback() {
    const img = DOM.videoStream;
    const iframe = DOM.videoFallback;
    if (!img || !iframe) return;

    // 초기 상태: iframe 숨김
    iframe.style.display = 'none';

    const showIframe = () => {
      iframe.style.display = 'block';
      img.style.display = 'none';
    };

    // 이미지 스트림이 에러일 경우 폴백
    img.addEventListener('error', showIframe, { once: true });

    // 혹시 이미지가 너무 작은 해상도로 오는 경우, DPI 상관없이 꽉 차지만
    // 특정 서버가 MJPEG이 아닌 HTML 페이지를 반환할 때도 에러 없이 로드될 수 있음.
    // 그런 경우 간단한 휴리스틱으로 전환 (자연 크기가 매우 작고 콘텐츠 타입이 불명확)
    let checked = false;
    const heuristicCheck = () => {
      if (checked) return;
      checked = true;
      try {
        if (img.naturalWidth && img.naturalHeight && (img.naturalWidth < 160 || img.naturalHeight < 90)) {
          showIframe();
        }
      } catch (_) {}
    };
    // 로드 후 점검
    img.addEventListener('load', heuristicCheck, { once: true });
    // 2초 내 미로드 시 폴백 시도
    setTimeout(() => {
      if (img.complete === false || img.naturalWidth === 0) {
        showIframe();
      }
    }, 2000);
  }
})();