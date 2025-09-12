// app.js

(() => {
  "use strict";

  // ==== 1. 설정 (Configuration) ====
  // 서버와 동기화가 필요한 주요 설정값들.
  // TODO: 서버(main.py)에서 웹소켓 연결 시 이 객체를 전송하도록 구현해야 합니다.
  const config = {
    RPM_MAX: 8000,
    SPEED_MAX: 100,
    RPM_IDLE_VALUE: 700,
    RPM_REDZONE_NORM: 7000 / 8000,
    AXIS_MIN: -50,
    AXIS_MAX: 50,
    AXIS_DEADZONE: 5.0, // config.py의 AXIS_DEADZONE_UNITS와 일치
    AXIS_SLEW_UP_PER_S: 140,
    AXIS_SLEW_DOWN_PER_S: 140,
    SEND_INTERVAL_MS: 70, // 서버 전송 주기
    TOAST_DURATION_MS: 2200,
    GAUGE_ANGLE_RANGE: 240, // 게이지 바늘의 총 회전 각도
  };

  // ==== 2. DOM 요소 선택 ====
  const DOMElements = {
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
    escStatus: document.getElementById("escStatus"),
  };

  // ==== 3. 애플리케이션 상태 관리 ====
  const state = {
    rpm_norm: 0,
    speed_pct: 0,
    gear: "P",
    virtual_gear: 1,  // 가상 기어 상태 추가
    head_on: false,
    engine_running: false,
    esc_armed: false,  // ESC 아밍 상태 추가
    sport_mode_on: false,
    shift_fail: false,
    axis: 0,
    steer_dir: 0,
    shift_state: "READY",
    torque_cmd: 0,
  };
  const keyState = {}; // 현재 눌린 키 상태
  const prev = { ...state }; // 변경 감지를 위한 이전 상태 저장 객체

  // ==== 4. 웹소켓 통신 ====
  let ws;
  let isConnected = false;
  let reconnectDelay = 1000;
  const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      isConnected = true;
      console.log("WebSocket connected.");
      reconnectDelay = 1000; // 연결 성공 시 재시도 딜레이 초기화
    };

    ws.onclose = () => {
      isConnected = false;
      console.log(`WebSocket disconnected. Retrying in ${reconnectDelay}ms...`);
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000); // Exponential backoff
    };

    ws.onmessage = (ev) => {
      console.log("서버 메시지 수신:", ev.data);
      handleServerMessage(ev.data);
    };
  }

  function send(data) {
    if (isConnected && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  // 주기적으로 서버에 RTT(왕복 시간) 체크를 위한 ping 전송
  setInterval(() => {
    send({ ping: performance.now() });
  }, 1000);
  
  function handleServerMessage(jsonData) {
    try {
      const msg = JSON.parse(jsonData);

      // Pong 메시지 처리 (네트워크 지연시간 계산)
      if (typeof msg.pong === "number") {
        updateNetworkLatency(performance.now() - msg.pong);
        return;
      }

      // 서버로부터 받은 힌트 메시지 토스트로 표시
      if (msg.engine_stop_hint) showToast(msg.engine_stop_hint);
      if (msg.brake_hint) showToast(msg.brake_hint);

      // 서버로부터 받은 차량 상태 업데이트
      if (typeof msg.virtual_rpm === "number") state.rpm_norm = msg.virtual_rpm;
      if (typeof msg.speed_pct === "number") state.speed_pct = msg.speed_pct;
      if (msg.gear) {
        state.gear = msg.gear;  // 기본 기어 상태 (P, R, N, D)
        if (msg.virtual_gear) state.virtual_gear = msg.virtual_gear;  // 가상 기어 상태
      }
      if (typeof msg.head_on === "boolean") state.head_on = msg.head_on;
      if (typeof msg.esc_armed === "boolean") state.esc_armed = msg.esc_armed;  // ESC 아밍 상태 추가
      if (typeof msg.sport_mode_on === "boolean") state.sport_mode_on = msg.sport_mode_on;
      if (msg.shift_state) state.shift_state = msg.shift_state;
      if (typeof msg.torque_cmd === "number") state.torque_cmd = msg.torque_cmd;
      
      // 서버가 보내준 확정된 엔진 상태로 UI 동기화
      if (typeof msg.engine_running === "boolean" && state.engine_running !== msg.engine_running) {
        state.engine_running = msg.engine_running;
        // 엔진 상태 변경 시 클러스터 전원도 함께 동기화
        setClusterPower(state.engine_running);
        if (state.engine_running) {
          onEngineStart();
          // 시동 시 P단으로 설정 (서버에서 이미 처리되지만 UI 동기화)
          if (state.gear !== "P") {
            state.gear = "P";
          }
        } else {
          onEngineStop();
        }
      }
      
      state.shift_fail = !!msg.shift_fail;

    } catch (e) {
      console.error("Failed to parse server message:", e);
    }
  }

  // ==== 5. 입력 처리 (키보드 & 버튼) ====
  
  // UI 버튼 이벤트 리스너
  DOMElements.gearButtons.forEach(b => b.addEventListener("click", () => send({ gear: b.dataset.gear })));
  DOMElements.btnHead.addEventListener("click", () => send({ head_toggle: true }));
  DOMElements.btnSport.addEventListener("click", () => send({ sport_mode_toggle: true }));
  DOMElements.btnEngine.addEventListener("click", () => {
    // 엔진 버튼은 서버 응답을 기다린 후 UI 업데이트 (일관성 보장)
    send({ engine_toggle: true });
  });

  // 키보드 이벤트 리스너
  window.addEventListener("keydown", (e) => {
    const key = e.key.toLowerCase();
    keyState[key] = true;
    
    // ESC 키 처리 (엔진 정지)
    if (key === "escape") {
      if (state.engine_running) {
        DOMElements.btnEngine.click();
      }
      return;
    }
    
    // 단축키 처리
    if ("prnd".includes(key)) send({ gear: key.toUpperCase() });
    if (key === "h") DOMElements.btnHead.click();
    if (key === "e") DOMElements.btnEngine.click();
    if (key === "m") DOMElements.btnSport.click();
    
  });
  window.addEventListener("keyup", (e) => { keyState[e.key.toLowerCase()] = false; });

  // ==== 6. 메인 루프 (입력 계산 및 서버 전송) ====
  let lastTimestamp = 0;
  let lastSendTime = 0;

  function mainLoop(timestamp) {
    if (!lastTimestamp) lastTimestamp = timestamp;
    const dt = (timestamp - lastTimestamp) / 1000.0;
    lastTimestamp = timestamp;

    // 키보드 입력에 따라 axis 값 조절
    const slewUp = config.AXIS_SLEW_UP_PER_S * dt;
    const slewDown = config.AXIS_SLEW_DOWN_PER_S * dt;
    if (keyState.w && !keyState.s) state.axis += slewUp;
    else if (keyState.s && !keyState.w) state.axis -= slewDown;
    state.axis = clamp(state.axis, config.AXIS_MIN, config.AXIS_MAX);

    // 조향값 계산
    state.steer_dir = (keyState.a && !keyState.d) ? -1 : (keyState.d && !keyState.a) ? 1 : 0;

    // 주기적으로 서버에 입력값 전송
    if (timestamp - lastSendTime >= config.SEND_INTERVAL_MS) {
      send({ axis: Math.round(state.axis), steer_dir: state.steer_dir });
      lastSendTime = timestamp;
    }
    
    // UI 렌더링
    render();
    requestAnimationFrame(mainLoop);
  }

  // ==== 7. 렌더링 및 UI 업데이트 ====
  let sweepAnimation = { active: false, start: 0, up: 700, down: 600 };

  function render() {
    // 엔진 시동 시 풀스윕 애니메이션 처리
    if (sweepAnimation.active) {
      renderSweepAnimation();
      return;
    }

    // 상태가 변경된 경우에만 DOM 업데이트
    if (prev.rpm_norm !== state.rpm_norm) updateGauge(DOMElements.needleRpm, DOMElements.readoutRpm, state.rpm_norm * config.RPM_MAX, config.RPM_MAX, "", state.rpm_norm >= config.RPM_REDZONE_NORM);
    if (prev.speed_pct !== state.speed_pct) updateGauge(DOMElements.needleSpeed, DOMElements.readoutSpeed, state.speed_pct, config.SPEED_MAX, "%");
    if (prev.gear !== state.gear || prev.virtual_gear !== state.virtual_gear) updateGear();
    if (prev.head_on !== state.head_on) DOMElements.btnHead.classList.toggle("on", state.head_on);
    if (prev.sport_mode_on !== state.sport_mode_on) updateSportMode();
    if (prev.axis !== state.axis) updateAxisBar();
    if (prev.shift_state !== state.shift_state) updateShiftState();
    if (prev.torque_cmd !== state.torque_cmd) updateTorqueCmd();
    if (prev.esc_armed !== state.esc_armed) updateEscStatus();
    
    // 엔진 상태가 변경된 경우는 이미 서버 메시지 처리에서 동기화됨
    // (중복 제거)
    
    if (state.shift_fail) {
      DOMElements.gearIndicator.classList.add("error");
      setTimeout(() => DOMElements.gearIndicator.classList.remove("error"), 400);
      state.shift_fail = false;
    }
    
    // 현재 상태를 이전 상태로 복사
    Object.assign(prev, state);
  }

  // --- 렌더링 헬퍼 함수 ---
  const clamp = (v, min, max) => v < min ? min : (v > max ? max : v);
  const valueToAngle = (value, max) => (clamp(value, 0, max) / max) * config.GAUGE_ANGLE_RANGE - (config.GAUGE_ANGLE_RANGE / 2);

  function updateGauge(needle, readout, value, max, unit = "", isRedzone = false) {
    needle.style.transform = `translate(-50%, -100%) rotate(${valueToAngle(value, max)}deg)`;
    needle.classList.toggle("redzone", isRedzone);
    readout.textContent = Math.round(value) + unit;
  }
  
  function updateGear() {
    // 기어 표시: D단일 때는 가상 기어 번호 표시, 아니면 기본 기어 표시
    const displayGear = (state.gear === "D" && state.virtual_gear) ? state.virtual_gear.toString() : state.gear;
    DOMElements.gearIndicator.textContent = displayGear;
    
    // 버튼 활성화: 기본 기어 상태로 비교
    DOMElements.gearButtons.forEach(el => {
      const isActive = el.dataset.gear === state.gear;
      el.classList.toggle("active", isActive);
      
      // 디버깅용 로그
      if (isActive) {
        console.log(`기어 버튼 활성화: ${el.dataset.gear} (현재 기어: ${state.gear})`);
      }
    });
    
    console.log(`기어 상태 업데이트: ${state.gear}, 가상기어: ${state.virtual_gear}, 표시: ${displayGear}`);
  }
  
  function updateSportMode() {
    DOMElements.body.classList.toggle("sport-mode-active", state.sport_mode_on);
    DOMElements.btnSport.classList.toggle("on", state.sport_mode_on);
  }
  
  function updateAxisBar() {
    const range = config.AXIS_MAX - config.AXIS_DEADZONE;
    const posPct = state.axis > config.AXIS_DEADZONE ? (state.axis - config.AXIS_DEADZONE) / range * 100 : 0;
    const negPct = state.axis < -config.AXIS_DEADZONE ? (-state.axis - config.AXIS_DEADZONE) / range * 100 : 0;
    DOMElements.axisBarFill.style.height = `${posPct}%`;
    DOMElements.axisBarFillNeg.style.height = `${negPct}%`;
    DOMElements.axisReadout.textContent = Math.round(state.axis);
  }
  
  function updateShiftState() {
    DOMElements.shiftState.textContent = state.shift_state;
    
    // D 기어에서만 변속 정보 표시
    if (state.gear === "D") {
      DOMElements.shiftInfo.style.display = "block";
      
      // 변속 상태에 따른 색상 변경
      DOMElements.shiftState.className = "shift-state";
      if (state.shift_state !== "READY") {
        DOMElements.shiftState.classList.add("shifting");
      }
    } else {
      DOMElements.shiftInfo.style.display = "none";
    }
  }
  
  function updateTorqueCmd() {
    DOMElements.torqueCmd.textContent = `${Math.round(state.torque_cmd)}%`;
    
    // 토크 방향에 따른 색상 변경
    DOMElements.torqueCmd.className = "torque-cmd";
    if (state.torque_cmd > 0) {
      DOMElements.torqueCmd.classList.add("positive");
    } else if (state.torque_cmd < 0) {
      DOMElements.torqueCmd.classList.add("negative");
    }
  }
  
  function updateEscStatus() {
    if (state.esc_armed) {
      DOMElements.escStatus.textContent = "ESC 준비 완료";
      DOMElements.escStatus.className = "esc-status ready";
    } else {
      DOMElements.escStatus.textContent = "ESC 준비 중...";
      DOMElements.escStatus.className = "esc-status arming";
    }
  }

  function updateNetworkLatency(rtt) {
    let color = "#8aff8a"; // good
    if (rtt >= 200) color = "#ff6b6b"; // bad
    else if (rtt >= 80) color = "#ffd866"; // warning
    DOMElements.netLatency.textContent = `${Math.round(rtt)} ms`;
    DOMElements.netLatency.style.color = color;
  }

  // --- 시동/정지 및 애니메이션 ---
  function setClusterPower(on) {
    DOMElements.body.classList.toggle("cluster-on", on);
    DOMElements.body.classList.toggle("cluster-off", !on);
  }

  function onEngineStart() {
    // 클러스터 전원은 이미 setClusterPower에서 처리됨
    sweepAnimation.active = true;
    sweepAnimation.start = performance.now();
  }

  function onEngineStop() {
    sweepAnimation.active = false;
    // 클러스터 전원은 이미 setClusterPower에서 처리됨
  }

  function renderSweepAnimation() {
    const elapsed = performance.now() - sweepAnimation.start;
    const { up, down } = sweepAnimation;
    const total = up + down;
    const easeInOut = t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

    let rpm, speed;
    if (elapsed < up) {
      const k = easeInOut(elapsed / up);
      rpm = k * config.RPM_MAX;
      speed = k * config.SPEED_MAX;
    } else {
      const k = easeInOut((elapsed - up) / down);
      rpm = (1 - k) * config.RPM_MAX;
      speed = (1 - k) * config.SPEED_MAX;
    }
    
    updateGauge(DOMElements.needleRpm, DOMElements.readoutRpm, rpm, config.RPM_MAX, "", (rpm / config.RPM_MAX) >= config.RPM_REDZONE_NORM);
    updateGauge(DOMElements.needleSpeed, DOMElements.readoutSpeed, speed, config.SPEED_MAX, "%");

    if (elapsed >= total) {
      sweepAnimation.active = false;
      // 애니메이션 종료 후 IDLE 상태로 복귀
      updateGauge(DOMElements.needleRpm, DOMElements.readoutRpm, config.RPM_IDLE_VALUE, config.RPM_MAX, "", (config.RPM_IDLE_VALUE / config.RPM_MAX) >= config.RPM_REDZONE_NORM);
      updateGauge(DOMElements.needleSpeed, DOMElements.readoutSpeed, 0, config.SPEED_MAX, "%");
    }
  }

  // --- 유틸리티 ---
  function showToast(msg) {
    const el = document.createElement("div");
    el.className = "toast-msg";
    el.textContent = msg;
    DOMElements.toast.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(-8px)";
    }, config.TOAST_DURATION_MS - 400);
    setTimeout(() => {
      DOMElements.toast.removeChild(el);
    }, config.TOAST_DURATION_MS);
  }
  
  // ==== 8. 애플리케이션 시작 ====
  document.addEventListener("DOMContentLoaded", () => {
    // 초기 상태: 클러스터 꺼짐 상태로 시작
    setClusterPower(false);
    connect();
    requestAnimationFrame(mainLoop);
  });

})();