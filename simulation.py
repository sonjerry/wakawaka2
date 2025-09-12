# simulation.py
import math
import random
import config
from enum import Enum

# --- 유틸리티 함수 ---
def clamp(x, a, b):
    """값을 특정 범위(a, b) 내로 제한합니다."""
    return a if x < a else (b if x > b else x)

def lerp(a, b, t):
    """선형 보간: t(0.0~1.0) 값에 따라 a와 b 사이의 값을 계산합니다."""
    t = clamp(t, 0.0, 1.0)
    return a + (b - a) * t

def s_curve(t):
    """S-curve 함수: 0에서 1까지 부드럽게 변화"""
    t = clamp(t, 0.0, 1.0)
    return 3 * t * t - 2 * t * t * t

# --- 변속 상태 열거형 ---
class ShiftState(Enum):
    READY = "READY"
    PRECUT = "PRECUT"
    CUT_HOLD = "CUT_HOLD"
    REENGAGE = "REENGAGE"
    JERK = "JERK"
    STABILIZE = "STABILIZE"

# --- 차량 모델 클래스 ---
class VehicleModel:
    """
    새로운 8단 변속기 시스템을 가진 차량 시뮬레이션 클래스.
    - 100Hz 루프 주기
    - 8단 자동 변속기 (기어비 기반)
    - vRPM 기반 변속 스케줄링
    - 변속 상태기계 (READY→PRECUT→CUT_HOLD→REENGAGE→JERK→STABILIZE)
    - 토크 제어 시스템 (가속/브레이크/크리프/엔진브레이크)
    """
    
    def __init__(self):
        # --- 기본 상태 ---
        self.steer_cur_us = float(config.STEER_CENTER_US)
        self.steer_target_us = float(config.STEER_CENTER_US)
        self.head_on = False
        self.sport_mode_on = False
        self.engine_running = False
        self.engine_cranking_timer = 0.0

        # --- 입력 상태 ---
        self.axis = 0.0  # -50..50 원본 입력
        self.axis_prev = 0.0  # 이전 프레임 입력 (슬루 제한용)
        self.steer_dir = 0
        
        # --- 기어 상태 ---
        self.gear = "P"  # "P", "R", "N", "D"
        self.virtual_gear = 1  # 1..8단 (D 기어에서만 사용)
        
        # --- 속도 및 vRPM ---
        self.wheel_speed = 0.0  # -1(후진)..1(전진) 정규화된 바퀴 속도
        self.speed_est = 0.0  # 속도 추정기 출력 (m/s)
        self.vrpm = 0.0  # 가상 RPM (실제 값)
        self.vrpm_norm = 0.0  # 0..1 정규화된 RPM (UI용)
        
        # --- 변속 상태기계 ---
        self.shift_state = ShiftState.READY
        self.shift_timer = 0.0  # 현재 변속 단계 타이머 (ms)
        self.shift_direction = 0  # 1: 업시프트, -1: 다운시프트
        self.shift_target_gear = 1  # 변속 목표 기어
        self.shift_torque_prev = 0.0  # 변속 전 토크 (PRECUT용)
        
        # --- 토크 제어 ---
        self.torque_cmd = 0.0  # 최종 토크 명령 (%)
        self.throttle_intent = 0.0  # 0..1 정규화된 스로틀 의도
        self.brake_intent = 0.0  # 0..1 정규화된 브레이크 의도
        
        # --- 파라미터 로드 ---
        self._load_parameters()

    def _load_parameters(self):
        """config.py에서 파라미터를 로드합니다."""
        # 기어비 및 토크 스케일
        self.gear_ratios = config.GEAR_RATIOS
        self.final_drive = config.FINAL_DRIVE
        self.gear_torque_scale = config.GEAR_TORQUE_SCALE
        self.gear_drag_scale = config.GEAR_DRAG_SCALE
        
        # vRPM 설정
        self.vrpm_idle = config.VRPM_IDLE
        self.vrpm_red = config.VRPM_RED
        self.vrpm_up_threshold = config.VRPM_UP_THRESHOLD
        self.vrpm_down_threshold = config.VRPM_DOWN_THRESHOLD
        self.vrpm_cut_hysteresis = config.VRPM_CUT_HYSTERESIS
        
        # 속도 추정기
        self.speed_estimator_gamma = config.SPEED_ESTIMATOR_GAMMA
        self.wheel_radius = config.WHEEL_RADIUS
        
        # 변속 타이밍 (ms를 초로 변환)
        self.shift_precut_ms = config.SHIFT_PRECUT_MS
        self.shift_cut_hold_ms = config.SHIFT_CUT_HOLD_MS
        self.shift_reengage_ms = config.SHIFT_REENGAGE_MS
        self.shift_jerk_ms = config.SHIFT_JERK_MS
        self.shift_stabilize_ms = config.SHIFT_STABILIZE_MS
        
        # 변속 토크 제어
        self.shift_precut_alpha = config.SHIFT_PRECUT_ALPHA
        self.shift_cut_torque = config.SHIFT_CUT_TORQUE
        self.shift_jerk_delta = config.SHIFT_JERK_DELTA
        
        # 토크 제어
        self.max_brake_torque = config.MAX_BRAKE_TORQUE
        self.max_drag_torque = config.MAX_DRAG_TORQUE
        self.creep_torque = config.CREEP_TORQUE
        self.creep_release_speed = config.CREEP_RELEASE_SPEED
        
        # 입력 처리
        self.input_deadzone = config.INPUT_DEADZONE
        self.input_slew_limit = config.INPUT_SLEW_LIMIT
        self.throttle_delay_rpm = config.THROTTLE_DELAY_RPM
        
        # RPM 설정
        self.RPM_MAX = config.RPM_SCALE_MAX
        self.RPM_IDLE = config.RPM_IDLE_VALUE / self.RPM_MAX
        self.RPM_CREEP = config.RPM_CREEP_VALUE / self.RPM_MAX
        self.RPM_FUELCUT = config.RPM_FUEL_CUT_VALUE / self.RPM_MAX
        self.RPM_R_MAX_R = config.REVERSE_RPM_MAX_VALUE / self.RPM_MAX
        
        # 물리 파라미터
        self.AXIS_DEADZONE = config.AXIS_DEADZONE_UNITS
        self.ENGINE_INERTIA = config.ENGINE_INERTIA
        
        # 가속/감속 및 저항 계수
        self.A_POS = 0.2
        self.A_NEG = 0.3
        self.D0 = 0.030
        self.D1 = 0.10
        self.D2 = 0.18
        self.MASS_K = 2.0

        # 스포츠 모드 파라미터
        self.SPORT_POS_SCALE = 1.6

    # --------- Public API (main.py에서 호출) ---------
    def update(self, dt: float, inputs: dict):
        """메인 업데이트 함수. 100Hz로 호출됩니다."""
        self._ingest_inputs(inputs)
        self._update_engine_state(dt)
        self._update_steering(dt, inputs)
        self._apply_gear_change(inputs)
        self._update_vehicle_system(dt)

    def get_state_snapshot(self, inputs: dict = None) -> dict:
        """웹 클라이언트에 보낼 현재 상태 딕셔너리를 반환합니다."""
        return {
            "virtual_rpm": clamp(self.vrpm_norm, 0.0, 1.0),
            "speed_pct": int(abs(self.wheel_speed) * 100),
            "gear": self.gear,
            "virtual_gear": self.virtual_gear if self.gear == "D" else 1,
            "head_on": self.head_on,
            "engine_running": self.engine_running,
            "sport_mode_on": self.sport_mode_on,
            "shift_state": self.shift_state.value if self.gear == "D" else "READY",
            "torque_cmd": round(self.torque_cmd, 1),
        }

    def get_hardware_outputs(self, inputs: dict = None) -> dict:
        """실제 하드웨어로 보낼 제어값 딕셔너리를 반환합니다."""
        braking = self.axis <= -self.AXIS_DEADZONE
        is_moving = self.gear in ('D', 'R')
        tail_brightness = 1.0 if (braking and is_moving) else (0.5 if self.head_on else 0.0)

        # ESC 출력 계산
        if self.gear == "D":
            esc_output = self.torque_cmd / 100.0  # %를 -1..1로 변환
        else:
            # R, P, N 기어는 기존 방식
            esc_output = self.wheel_speed
        
        # 엔진이 꺼져있으면 ESC 출력은 0
        if not self.engine_running:
            esc_output = 0.0

        return {
            "steering_us": int(self.steer_cur_us),
            "esc_norm": esc_output,
            "head_brightness": 1.0 if self.head_on else 0.0,
            "tail_brightness": tail_brightness,
        }

    # --------- 내부 서브시스템 업데이트 함수 ---------
    def _ingest_inputs(self, inputs: dict):
        """입력값을 처리하고 슬루 제한을 적용합니다."""
        new_axis = clamp(float(inputs.get("axis", 0.0)), -50.0, 50.0)
        
        # 슬루 제한 적용
        axis_delta = new_axis - self.axis_prev
        axis_delta = clamp(axis_delta, -self.input_slew_limit, self.input_slew_limit)
        self.axis = self.axis_prev + axis_delta
        self.axis_prev = self.axis
        
        # 의도 분류
        if abs(self.axis) < self.input_deadzone:
            self.throttle_intent = 0.0
            self.brake_intent = 0.0
        else:
            self.throttle_intent = max(self.axis, 0.0) / 50.0
            self.brake_intent = max(-self.axis, 0.0) / 50.0

    def _update_engine_state(self, dt: float):
        """엔진 상태를 업데이트합니다."""
        if self.engine_cranking_timer > 0.0:
            self.engine_cranking_timer -= dt
            if self.engine_cranking_timer <= 0.0:
                self.engine_running = True
        
        if not self.engine_running:
            if self.engine_cranking_timer > 0.0:
                self.vrpm_norm = clamp(0.03 + random.uniform(-0.02, 0.02), 0.0, 1.0)
            else:
                self.vrpm_norm = 0.0

    def _update_steering(self, dt: float, inputs: dict):
        """조향을 업데이트합니다."""
        allow_steer = bool(getattr(config, "ALLOW_STEER_WHEN_ENGINE_ON", True))
        steer_dir = 0
        if (allow_steer and self.engine_running) or (self.gear != "P"):
            steer_dir = int(inputs.get("steer_dir", 0))

        if steer_dir == -1: self.steer_target_us = config.STEER_LEFT_US
        elif steer_dir == 1: self.steer_target_us = config.STEER_RIGHT_US
        else: self.steer_target_us = config.STEER_CENTER_US
        
        max_step = float(getattr(config, "STEER_SPEED_US_PER_S", 1000.0)) * dt
        d = self.steer_target_us - self.steer_cur_us
        self.steer_cur_us += clamp(d, -max_step, max_step)
        
    def _apply_gear_change(self, inputs: dict):
        """기어 변경을 처리합니다."""
        new_gear = inputs.get("gear")
        if new_gear and new_gear != self.gear:
            if new_gear in ("P", "N"):
                self.gear = new_gear
                self.wheel_speed = 0.0
                self._reset_shift_state()
            elif new_gear in ("R", "D") and (self.gear in ("R", "D") or self.axis <= -self.AXIS_DEADZONE):
                is_direction_change = (self.gear in ('D','R') and self.gear != new_gear)
                self.gear = new_gear
                if new_gear == "D":
                    self.virtual_gear = 1
                self._reset_shift_state()
                if is_direction_change:
                    self.wheel_speed = 0.0
            else:
                inputs["shift_fail"] = True

    def _reset_shift_state(self):
        """변속 상태를 초기화합니다."""
        self.shift_state = ShiftState.READY
        self.shift_timer = 0.0
        self.shift_direction = 0
        self.shift_target_gear = self.virtual_gear

    def _update_vehicle_system(self, dt: float):
        """통합된 차량 시스템을 업데이트합니다."""
        # 1. 속도 추정기 업데이트
        self._update_speed_estimator(dt)
        
        # 2. vRPM 계산
        self._update_vrpm()
        
        # 3. D 기어에서만 변속 스케줄링
        if self.gear == "D":
            self._update_shift_scheduling()
            self._update_shift_state_machine(dt)
        
        # 4. 토크 제어
        self._update_torque_control(dt)
        
        # 5. 물리 시뮬레이션
        self._update_physics(dt)
        
        # 6. RPM 정규화 업데이트 (UI용)
        self._update_rpm_normalization()

    def _update_speed_estimator(self, dt: float):
        """속도 추정기를 업데이트합니다."""
        # 스로틀 의도를 속도 명령으로 변환 (브레이크는 별도 처리)
        if self.brake_intent > 0.0:
            # 브레이크 입력: 속도를 감소시킴
            speed_demand = -self.brake_intent * 5.0  # 최대 5 m/s 감속
        else:
            # 스로틀 입력: 속도를 증가시킴
            speed_demand = self.throttle_intent * 10.0  # 최대 10 m/s
        
        # 1차 지연 필터
        alpha = clamp(dt / (1.0 / self.speed_estimator_gamma), 0.0, 1.0)
        self.speed_est = (1 - alpha) * self.speed_est + alpha * speed_demand
        
        # 바퀴 속도로 변환
        self.wheel_speed = clamp(self.speed_est / 10.0, -1.0, 1.0)

    def _update_vrpm(self):
        """vRPM을 계산합니다."""
        if not self.engine_running:
            self.vrpm = 0.0
            return
        
        # 바퀴 각속도 계산 (rad/s)
        wheel_rad_s = self.speed_est / self.wheel_radius
        
        if self.gear == "D" and 1 <= self.virtual_gear <= 8:
            # D 기어: 기어비 적용
            gear_ratio = self.gear_ratios[self.virtual_gear - 1]
            total_ratio = gear_ratio * self.final_drive
            self.vrpm = wheel_rad_s * total_ratio * 60.0 / (2.0 * math.pi)
        elif self.gear == "R":
            # R 기어: 고정 기어비
            self.vrpm = wheel_rad_s * 3.0 * 60.0 / (2.0 * math.pi)  # R 기어는 3.0 기어비 가정
        else:
            # P, N 기어: IDLE RPM
            self.vrpm = self.vrpm_idle
        
        # 하한 적용
        self.vrpm = max(self.vrpm, self.vrpm_idle)

    def _update_shift_scheduling(self):
        """변속 스케줄링을 처리합니다."""
        if self.shift_state != ShiftState.READY:
            return  # 변속 중이면 스케줄링 안함
        
        if self.vrpm < self.vrpm_idle:
            return  # RPM이 너무 낮으면 변속 안함
        
        # 업시프트 체크
        if (self.virtual_gear < 8 and 
            self.vrpm >= self.vrpm_up_threshold and
            not self.brake_intent > 0.5):
            
            # 스로틀이 높으면 약간 지연
            if self.throttle_intent > 0.7 and self.vrpm < self.vrpm_up_threshold + self.throttle_delay_rpm:
                return
            
            self._request_shift(1)  # 업시프트
            return
        
        # 다운시프트 체크
        if (self.virtual_gear > 1 and 
            (self.vrpm <= self.vrpm_down_threshold or self.brake_intent > 0.5)):
            
            # 안전 검사: 다음 기어에서 레드라인 초과하지 않는지
            next_gear = self.virtual_gear - 1
            if next_gear >= 1:
                next_ratio = self.gear_ratios[next_gear - 1]
                current_ratio = self.gear_ratios[self.virtual_gear - 1]
                expected_vrpm = self.vrpm * (next_ratio / current_ratio)
                
                if expected_vrpm <= self.vrpm_red:
                    self._request_shift(-1)  # 다운시프트

    def _request_shift(self, direction: int):
        """변속 요청을 처리합니다."""
        if self.shift_state != ShiftState.READY:
            return
        
        self.shift_direction = direction
        self.shift_target_gear = self.virtual_gear + direction
        self.shift_target_gear = clamp(self.shift_target_gear, 1, 8)
        
        if self.shift_target_gear != self.virtual_gear:
            self.shift_state = ShiftState.PRECUT
            self.shift_timer = 0.0
            self.shift_torque_prev = self.torque_cmd

    def _update_shift_state_machine(self, dt: float):
        """변속 상태기계를 업데이트합니다."""
        if self.shift_state == ShiftState.READY:
            return
        
        self.shift_timer += dt * 1000.0  # ms로 변환
        
        if self.shift_state == ShiftState.PRECUT:
            if self.shift_timer >= self.shift_precut_ms:
                self.shift_state = ShiftState.CUT_HOLD
                self.shift_timer = 0.0
                
        elif self.shift_state == ShiftState.CUT_HOLD:
            if self.shift_timer >= self.shift_cut_hold_ms:
                # 기어 변경
                self.virtual_gear = self.shift_target_gear
                self.shift_state = ShiftState.REENGAGE
                self.shift_timer = 0.0
                
        elif self.shift_state == ShiftState.REENGAGE:
            if self.shift_timer >= self.shift_reengage_ms:
                self.shift_state = ShiftState.JERK
                self.shift_timer = 0.0
                
        elif self.shift_state == ShiftState.JERK:
            if self.shift_timer >= self.shift_jerk_ms:
                self.shift_state = ShiftState.STABILIZE
                self.shift_timer = 0.0
                
        elif self.shift_state == ShiftState.STABILIZE:
            if self.shift_timer >= self.shift_stabilize_ms:
                self.shift_state = ShiftState.READY
                self.shift_timer = 0.0

    def _update_torque_control(self, dt: float):
        """토크 제어를 업데이트합니다."""
        # 1. 레드라인 컷 체크 (최우선)
        if self.vrpm >= self.vrpm_red:
            self.torque_cmd = 0.0
            return
        
        # 2. 브레이크 우선
        if self.brake_intent > 0.0:
            # D 기어에서는 브레이크 시 토크를 0으로 설정 (후진 방지)
            # R 기어에서는 후진 토크 허용
            if self.gear == "D":
                self.torque_cmd = 0.0
            else:
                self.torque_cmd = -self.brake_intent * self.max_brake_torque
            return
        
        # 3. 변속 중 토크 제어 (D 기어에서만)
        if self.gear == "D" and self.shift_state != ShiftState.READY:
            self.torque_cmd = self._calculate_shift_torque()
            return
        
        # 4. 기본 토크 계산
        base_torque = self._calculate_base_torque()
        
        # 5. 크리프 토크 (D 기어에서만)
        creep_torque = self._calculate_creep_torque()
        
        # 6. 엔진 브레이크
        drag_torque = self._calculate_drag_torque()
        
        # 7. 최종 토크 명령
        self.torque_cmd = base_torque + creep_torque + drag_torque
        
        # 8. 기어별 제한 적용
        if self.gear == "D":
            self.torque_cmd = clamp(self.torque_cmd, 0.0, 100.0)  # D 기어: 양수만
        elif self.gear == "R":
            self.torque_cmd = clamp(self.torque_cmd, -100.0, 0.0)  # R 기어: 음수만
        else:
            self.torque_cmd = 0.0  # P, N 기어: 토크 없음

    def _calculate_shift_torque(self) -> float:
        """변속 중 토크를 계산합니다."""
        if self.shift_state == ShiftState.PRECUT:
            return self.shift_torque_prev * self.shift_precut_alpha
        elif self.shift_state == ShiftState.CUT_HOLD:
            return self.shift_cut_torque
        elif self.shift_state == ShiftState.REENGAGE:
            # S-curve로 목표 토크까지 복원
            progress = clamp(self.shift_timer / self.shift_reengage_ms, 0.0, 1.0)
            s_progress = s_curve(progress)
            target_torque = self._calculate_base_torque()
            return lerp(self.shift_cut_torque, target_torque, s_progress)
        elif self.shift_state == ShiftState.JERK:
            target_torque = self._calculate_base_torque()
            return target_torque + self.shift_jerk_delta
        elif self.shift_state == ShiftState.STABILIZE:
            return self._calculate_base_torque()
        else:
            return 0.0

    def _calculate_base_torque(self) -> float:
        """기본 토크를 계산합니다."""
        if self.gear == "D" and 1 <= self.virtual_gear <= 8:
            gear_scale = self.gear_torque_scale[self.virtual_gear - 1]
            return self.throttle_intent * 100.0 * gear_scale
        elif self.gear == "R":
            return -self.throttle_intent * 100.0  # R 기어는 음수 토크
        else:
            return 0.0

    def _calculate_creep_torque(self) -> float:
        """크리프 토크를 계산합니다."""
        if (self.gear == "D" and 
            self.throttle_intent == 0.0 and 
            self.brake_intent == 0.0 and 
            self.speed_est < self.creep_release_speed):
            return self.creep_torque
        return 0.0

    def _calculate_drag_torque(self) -> float:
        """엔진 브레이크 토크를 계산합니다."""
        if (self.throttle_intent == 0.0 and 
            self.brake_intent == 0.0 and 
            self.speed_est > 0.1):
            
            if self.gear == "D" and 1 <= self.virtual_gear <= 8:
                drag_scale = self.gear_drag_scale[self.virtual_gear - 1]
                return -self.max_drag_torque * drag_scale
            elif self.gear == "R":
                return -self.max_drag_torque * 0.5  # R 기어는 절반 드래그
        return 0.0

    def _update_physics(self, dt: float):
        """물리 시뮬레이션을 업데이트합니다."""
        # 토크 명령을 가속도로 변환
        a_cmd = self.torque_cmd / 100.0  # %를 -1..1로 변환
        
        if self.sport_mode_on and self.throttle_intent > 0:
            a_cmd *= self.SPORT_POS_SCALE
        
        # 기존 저항 계산
        v = self.wheel_speed
        drag = (self.D0 * math.copysign(1, v)) + (self.D1 * v) + (self.D2 * v * abs(v))
        
        # 최종 가속도
        a = (a_cmd - drag) * self.MASS_K
        new_wheel_speed = self.wheel_speed + a * dt
        
        # 기어별 방향 제한
        if self.gear == "D":
            new_wheel_speed = max(0.0, new_wheel_speed)  # D 기어: 전진만
        elif self.gear == "R":
            new_wheel_speed = min(0.0, new_wheel_speed)  # R 기어: 후진만
        
        self.wheel_speed = clamp(new_wheel_speed, -1.0, 1.0)

    def _update_rpm_normalization(self):
        """RPM을 정규화하여 UI에 전달합니다."""
        if not self.engine_running:
            self.vrpm_norm = 0.0
            return
        
        # vRPM을 0..1 범위로 정규화
        self.vrpm_norm = clamp(self.vrpm / self.RPM_MAX, 0.0, 1.0)