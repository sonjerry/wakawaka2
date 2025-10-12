// static/app.js
// 최소 구현: 키/버튼/레이싱 휠 입력 → 서버 전송, 조향은 steer_delta(자동 복귀 없음), 불필요 코드 제거

(() => {
  "use strict";

  // ===== 설정 =====
  const AXIS_MIN = -50;
  const AXIS_MAX = 50;
  const AXIS_RATE_PER_S = 15;     // W/S 누르고 있을 때 초당 변화량 (40 -> 15로 감소)
  const SEND_INTERVAL_MS = 70;     // axis 전송 주기
  const STEER_STEP_DEG = 2;        // 조향 변화량(도) - 더 빠른 조향을 위해 증가 (1 -> 3)
  const STEER_SEND_MS = 17;        // 조향 전송 주기 - 더 빠른 조향을 위해 감소 (17 -> 12)
  
  // ===== 레이싱 휠 설정 =====
  const WHEEL_STEER_DEADZONE = 0.02;  // 스티어링 데드존
  const WHEEL_PEDAL_DEADZONE = 0.05;  // 페달 데드존
  let WHEEL_STEER_SENSITIVITY = 0.35; // 조향 민감도 (핸들 최대 회전 시 ±66도 도달) - 실시간 조정 가능
  const WHEEL_AXIS_RATE = 80;         // 레이싱 휠 페달 반응 속도

  // ===== DOM =====
  const DOM = {
    body: document.body,
    videoStream: document.getElementById("videoStream"),
    videoFallback: document.getElementById("videoFallback"),
    gearIndicator: document.getElementById("gearIndicator"),
    gearButtons: [...document.querySelectorAll(".gear-btn")],
    btnHead: document.getElementById("btnHead"),
    btnSport: document.getElementById("btnSport"),
    readyIndicator: document.getElementById("readyIndicator"),
    axisBarFill: document.getElementById("axisBarFill"),
    axisBarFillNeg: document.getElementById("axisBarFillNeg"),
    axisReadout: document.getElementById("axisReadout"),
    netLatency: document.getElementById("netLatency"),
    dbgSteer: document.getElementById("dbgSteer"),
    dbgThrottle: document.getElementById("dbgThrottle"),
    dbgWheel: document.getElementById("dbgWheel"),
    speedValue: document.getElementById("speedValue"),
    carWheelFL: document.getElementById("carWheelFL"),
    carWheelFR: document.getElementById("carWheelFR"),
    carVisualWrapper: document.querySelector('.car-visual'),
    wheelSettings: document.getElementById("wheelSettings"),
    wheelSensitivity: document.getElementById("wheelSensitivity"),
    wheelSensitivityValue: document.getElementById("wheelSensitivityValue"),
  };

  // ===== 상태 =====
  const state = {
    engine_running: true, // 접속=READY 개념으로 사용한 플래그(내부용)
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

  // ===== 레이싱 휠 상태 =====
  let wheelConnected = false;
  let wheelGamepad = null;
  let lastWheelSteerAngle = 0;
  let wheelAxisTarget = 0;

  // 웰컴 애니메이션 제거됨

  // ===== WebSocket =====
  let ws;
  let isConnected = false;
  let reconnectDelay = 1000;
  const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";

  // ===== READY 인디케이터 상태머신 =====
  function setReadyState(stateName) {
    const el = DOM.readyIndicator;
    if (!el) return;
    el.classList.remove('on', 'off', 'ready', 'connecting', 'reconnecting');
    switch (stateName) {
      case 'ready':
        el.textContent = 'READY';
        el.classList.add('on', 'ready');
        setClusterPower(true);
        break;
      case 'connecting':
        el.textContent = 'CONNECTING…';
        el.classList.add('connecting', 'off');
        setClusterPower(false);
        break;
      case 'reconnecting':
        el.textContent = 'RECONNECTING…';
        el.classList.add('reconnecting', 'off');
        setClusterPower(false);
        break;
      default:
        el.textContent = 'OFF';
        el.classList.add('off');
        setClusterPower(false);
    }
  }

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      isConnected = true;
      reconnectDelay = 1000;
      // 접속 완료 → READY 표시
      setReadyState('ready');
    };

    ws.onclose = () => {
      isConnected = false;
      setReadyState('reconnecting');
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    ws.onerror = () => {
      setReadyState('reconnecting');
    };

    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }

      if (typeof msg.pong === "number") {
        updateNetworkLatency(performance.now() - msg.pong);
        return;
      }
      // engine_running 개념 무시 (READY는 접속 기준)
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

  // 스포츠 모드 토글: 악센트 색상/약간의 강조
  DOM.btnSport && DOM.btnSport.addEventListener("click", () => {
    const on = !DOM.body.classList.contains('sport-mode-active');
    DOM.body.classList.toggle('sport-mode-active', on);
    DOM.btnSport.classList.toggle('on', on);
  });

  // ===== 키보드 이벤트 =====
  window.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    if (k in keyState && keyState[k]) return; // 중복 입력 방지
    if (k in keyState) keyState[k] = true;

    // 키보드로 기어 변경 기능 제거 (충돌 방지)
    if (k === "h") DOM.btnHead.click();
  });

  window.addEventListener("keyup", (e) => {
    const k = e.key.toLowerCase();
    if (k in keyState) keyState[k] = false;
  });

  // ===== 레이싱 휠 감지 및 입력 처리 =====
  window.addEventListener("gamepadconnected", (e) => {
    console.log("레이싱 휠 연결됨:", e.gamepad.id);
    console.log("축 개수:", e.gamepad.axes.length, "버튼 개수:", e.gamepad.buttons.length);
    console.log("");
    console.log("=== 포스 피드백(FFB) 센터링 줄이는 방법 ===");
    console.log("1. Logitech Gaming Software 실행");
    console.log("2. Driving Force GT 선택");
    console.log("3. '전체 게임 프로파일 설정' 탭");
    console.log("4. '스프링 효과 활성화' 체크 해제 또는 강도 20% 이하로 조정");
    console.log("5. '센터링 스프링' 강도 0~20% 로 조정");
    console.log("");
    
    wheelConnected = true;
    wheelGamepad = e.gamepad;
    
    // 휠 설정 UI 표시
    if (DOM.wheelSettings) {
      DOM.wheelSettings.style.display = 'block';
    }
    
    showToast("레이싱 휠 연결됨: " + e.gamepad.id, 3000);
  });

  window.addEventListener("gamepaddisconnected", (e) => {
    console.log("레이싱 휠 연결 해제됨:", e.gamepad.id);
    wheelConnected = false;
    wheelGamepad = null;
    
    // 휠 설정 UI 숨김
    if (DOM.wheelSettings) {
      DOM.wheelSettings.style.display = 'none';
    }
    
    showToast("레이싱 휠 연결 해제됨", 2000);
  });
  
  // 휠 민감도 슬라이더 이벤트
  if (DOM.wheelSensitivity) {
    DOM.wheelSensitivity.addEventListener('input', (e) => {
      WHEEL_STEER_SENSITIVITY = parseFloat(e.target.value);
      if (DOM.wheelSensitivityValue) {
        DOM.wheelSensitivityValue.textContent = `${Math.round(WHEEL_STEER_SENSITIVITY * 100)}%`;
      }
      console.log(`조향 민감도 변경: ${WHEEL_STEER_SENSITIVITY} (핸들 ±1.0 → RC카 ±${(WHEEL_STEER_SENSITIVITY * 66).toFixed(1)}°)`);
    });
  }

  function getGamepad() {
    if (!wheelConnected) return null;
    const gamepads = navigator.getGamepads();
    for (let gp of gamepads) {
      if (gp && gp.connected) return gp;
    }
    return null;
  }

  function applyDeadzone(value, deadzone) {
    if (Math.abs(value) < deadzone) return 0;
    const sign = value < 0 ? -1 : 1;
    return sign * (Math.abs(value) - deadzone) / (1 - deadzone);
  }

  // 버튼 상태 추적 (중복 입력 방지)
  const wheelState = {
    btn0Pressed: false,
    btn4Pressed: false,
    btn5Pressed: false,
    axesLogged: false,
    lastLogTime: 0,
    lastSteerLogTime: 0,
    lastGasAxis: 0,
    lastBrakeAxis: 0,
    lastGasRaw: 0,
    lastBrakeRaw: 0
  };

  function processWheelInput(dt) {
    const gp = getGamepad();
    if (!gp || !gp.axes || gp.axes.length < 1) return false;

    // Logitech Driving Force GT 매핑:
    // Axis 0: 스티어링 휠 (-1=왼쪽, +1=오른쪽)
    // Axis 1: 가속 페달 (-1=안 누름, +1=완전히 누름)
    // Axis 2: 브레이크 페달 (-1=안 누름, +1=완전히 누름)
    
    // 디버깅: 모든 축 정보 출력 (처음 한 번만)
    if (!wheelState.axesLogged && gp.axes) {
      console.log("=== 레이싱 휠 축 정보 ===");
      gp.axes.forEach((axis, i) => {
        console.log(`Axis ${i}: ${axis.toFixed(3)}`);
      });
      console.log(`조향 민감도: ${WHEEL_STEER_SENSITIVITY} (핸들 ±1.0 → RC카 ±${(WHEEL_STEER_SENSITIVITY * 66).toFixed(1)}°)`);
      wheelState.axesLogged = true;
    }
    
    // 스티어링 입력
    let steerRaw = gp.axes[0] || 0;
    steerRaw = applyDeadzone(steerRaw, WHEEL_STEER_DEADZONE);
    
    // 스티어링을 각도로 변환 (-1~1 → -66~66도)
    const STEER_MIN = -66;
    const STEER_MAX = 66;
    const targetSteerAngle = steerRaw * STEER_MAX * WHEEL_STEER_SENSITIVITY;
    
    // 주기적으로 조향각 범위 출력
    if (!wheelState.lastSteerLogTime || (performance.now() - wheelState.lastSteerLogTime) > 2000) {
      if (Math.abs(steerRaw) > 0.1) { // 조향 중일 때만
        console.log(`조향 입력: 원시값 ${gp.axes[0].toFixed(3)} → 데드존 적용 ${steerRaw.toFixed(3)} → RC카 각도 ${targetSteerAngle.toFixed(1)}°`);
      }
      wheelState.lastSteerLogTime = performance.now();
    }
    
    // 이전 조향각과 비교하여 변화량 전송
    const steerDelta = targetSteerAngle - lastWheelSteerAngle;
    if (Math.abs(steerDelta) > 0.5) { // 0.5도 이상 변화 시에만 전송
      send({ steer_delta: Math.round(steerDelta) });
      lastWheelSteerAngle = targetSteerAngle;
    }

    // 페달 입력 처리
    let gasRaw = 0;
    let brakeRaw = 0;
    
    // Logitech Driving Force GT 페달 처리
    if (gp.axes.length >= 2) {
      const gasAxis = gp.axes[1] !== undefined ? gp.axes[1] : -1;
      const brakeAxis = gp.axes[2] !== undefined ? gp.axes[2] : -1;
      
      // 페달 범위 확인 및 변환
      // 대부분의 Logitech 휠: -1(안 누름) ~ +1(완전히 누름)
      // 일부 브라우저/드라이버: 0(안 누름) ~ +1(완전히 누름)
      
      // 가속 페달: -1 또는 0을 기준으로 정규화
      if (gasAxis < -0.9) {
        // -1 기준: -1(안 누름) ~ +1(누름) → 0~1
        gasRaw = (gasAxis + 1) / 2;
      } else if (gasAxis >= -0.1) {
        // 0 기준: 0(안 누름) ~ +1(누름) → 0~1
        gasRaw = gasAxis;
      } else {
        // 중간값인 경우 0으로 처리
        gasRaw = 0;
      }
      
      // 브레이크 페달: 동일한 로직
      if (brakeAxis < -0.9) {
        // -1 기준
        brakeRaw = (brakeAxis + 1) / 2;
      } else if (brakeAxis >= -0.1) {
        // 0 기준
        brakeRaw = brakeAxis;
      } else {
        // 중간값인 경우 0으로 처리
        brakeRaw = 0;
      }
      
      // 디버깅 정보 저장
      wheelState.lastGasAxis = gasAxis;
      wheelState.lastBrakeAxis = brakeAxis;
      wheelState.lastGasRaw = gasRaw;
      wheelState.lastBrakeRaw = brakeRaw;
    }
    
    // 데드존 적용
    gasRaw = applyDeadzone(gasRaw, WHEEL_PEDAL_DEADZONE);
    brakeRaw = applyDeadzone(brakeRaw, WHEEL_PEDAL_DEADZONE);
    
    // 페달 입력을 axis 값으로 변환
    // 가속 페달 → 양수 (0~50), 브레이크 → 음수 (-50~0)
    wheelAxisTarget = (gasRaw * AXIS_MAX) - (brakeRaw * Math.abs(AXIS_MIN));
    wheelAxisTarget = clamp(wheelAxisTarget, AXIS_MIN, AXIS_MAX);
    
    // 디버깅: 페달 원시값 주기적 출력
    if (!wheelState.lastLogTime || (performance.now() - wheelState.lastLogTime) > 1000) {
      console.log(`페달 원시값 - 가속[1]: ${wheelState.lastGasAxis.toFixed(3)}, 브레이크[2]: ${wheelState.lastBrakeAxis.toFixed(3)}`);
      console.log(`  → 변환: 가속 ${wheelState.lastGasRaw.toFixed(3)}, 브레이크 ${wheelState.lastBrakeRaw.toFixed(3)}`);
      console.log(`  → 데드존 후: 가속 ${gasRaw.toFixed(3)}, 브레이크 ${brakeRaw.toFixed(3)}`);
      console.log(`  → 최종 axis: ${wheelAxisTarget.toFixed(1)}`);
      wheelState.lastLogTime = performance.now();
    }
    
    // UI 디버깅 정보 업데이트
    if (DOM.dbgWheel) {
      DOM.dbgWheel.textContent = `G:${(gasRaw * 100).toFixed(0)}% B:${(brakeRaw * 100).toFixed(0)}%`;
    }
    
    // 버튼 입력 처리 (기어 변경)
    // 일반적인 레이싱 휠 버튼 매핑:
    // - 버튼 0~3: 기본 버튼
    // - 버튼 4,5: 패들 시프터 (L/R)
    // - 버튼 12~15: 십자키
    if (gp.buttons && gp.buttons.length > 0) {
      // 패들 시프터: 버튼 4(업시프트), 버튼 5(다운시프트)
      if (gp.buttons[4] && gp.buttons[4].pressed && !wheelState.btn4Pressed) {
        wheelState.btn4Pressed = true;
        shiftGearUp();
      } else if (!gp.buttons[4] || !gp.buttons[4].pressed) {
        wheelState.btn4Pressed = false;
      }
      
      if (gp.buttons[5] && gp.buttons[5].pressed && !wheelState.btn5Pressed) {
        wheelState.btn5Pressed = true;
        shiftGearDown();
      } else if (!gp.buttons[5] || !gp.buttons[5].pressed) {
        wheelState.btn5Pressed = false;
      }
      
      // 전조등 토글: 버튼 0 (휠의 메인 버튼)
      if (gp.buttons[0] && gp.buttons[0].pressed && !wheelState.btn0Pressed) {
        wheelState.btn0Pressed = true;
        DOM.btnHead.click();
      } else if (!gp.buttons[0] || !gp.buttons[0].pressed) {
        wheelState.btn0Pressed = false;
      }
    }
    
    return true; // 레이싱 휠이 활성 상태임을 반환
  }
  
  // 기어 변경 헬퍼 함수
  function shiftGearUp() {
    const gears = ['P', 'R', 'N', 'D'];
    const currentIdx = gears.indexOf(state.gear);
    if (currentIdx < gears.length - 1) {
      send({ gear: gears[currentIdx + 1] });
    }
  }
  
  function shiftGearDown() {
    const gears = ['P', 'R', 'N', 'D'];
    const currentIdx = gears.indexOf(state.gear);
    if (currentIdx > 0) {
      send({ gear: gears[currentIdx - 1] });
    }
  }

  function showToast(message, duration = 2000) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), duration);
  }

  // ===== 조향: A/D 누르는 동안 주기적으로 steer_delta 전송 (자동 복귀 없음) =====
  let steerTimer = null;
  function updateSteerLoop() {
    // 레이싱 휠이 연결되어 있으면 키보드 조향 비활성화
    if (wheelConnected && getGamepad()) {
      if (steerTimer) {
        clearInterval(steerTimer);
        steerTimer = null;
      }
      return;
    }
    
    // 키보드 조향 처리
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
    const dt = 1 / 60; // 간단히 고정 step
    
    // 레이싱 휠 입력 처리 (우선순위)
    const wheelActive = processWheelInput(dt);
    
    if (wheelActive) {
      // 레이싱 휠이 활성 상태면 휠 입력 사용
      // 부드러운 전환을 위해 스무딩 적용
      const alpha = 1 - Math.exp(-dt / 0.05); // 50ms 타임상수
      state.axis += (wheelAxisTarget - state.axis) * alpha;
      state.axis = clamp(state.axis, AXIS_MIN, AXIS_MAX);
    } else {
      // 레이싱 휠이 없으면 키보드 입력 사용
      if (keyState.w && !keyState.s) {
        state.axis = clamp(state.axis + AXIS_RATE_PER_S * dt, AXIS_MIN, AXIS_MAX);
      } else if (keyState.s && !keyState.w) {
        state.axis = clamp(state.axis - AXIS_RATE_PER_S * dt, AXIS_MIN, AXIS_MAX);
      }
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
    DOM.gearIndicator.textContent = state.gear;
    DOM.gearButtons.forEach(el => el.classList.toggle("active", el.dataset.gear === state.gear));
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
    setReadyState('connecting');
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