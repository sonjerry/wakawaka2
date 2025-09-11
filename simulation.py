# simulation.py
import math
import random
import config

# --- 유틸리티 함수 ---
def clamp(x, a, b):
    """값을 특정 범위(a, b) 내로 제한합니다."""
    return a if x < a else (b if x > b else x)

def lerp(a, b, t):
    """선형 보간: t(0.0~1.0) 값에 따라 a와 b 사이의 값을 계산합니다."""
    t = clamp(t, 0.0, 1.0)
    return a + (b - a) * t

# --- 차량 모델 클래스 ---
class VehicleModel:
    """
    차량의 물리 및 상태를 시뮬레이션하는 클래스.
    - 실제 물리 속도는 wheel_speed 하나로 관리 (가속/드래그 적분)
    - 가상 RPM/기어는 계기판 표시용으로, 실제 속도 계산과는 분리
    - 변속 헌팅(빠르게 업/다운 반복) 방지 로직 포함 (LOCK + DWELL + SMOOTH)
    """
    def __init__(self):
        # --- 조향 / 램프 / 엔진 상태 ---
        self.steer_cur_us = float(config.STEER_CENTER_US)
        self.steer_target_us = float(config.STEER_CENTER_US)
        self.head_on = False
        self.sport_mode_on = False
        self.engine_running = False
        self.engine_cranking_timer = 0.0

        # --- 계기판 표시 전용 상태 (시각적) ---
        self.virtual_rpm = 0.0     # 0..1 정규화된 RPM
        self.virtual_gear = 1      # 1..9단 가상 기어
        self.shift_timer = 0.0     # 변속 연출(토크컷) 타이머
        self.shift_lock_timer = 0.0 # LOCK: 변속 중 평가 금지 타이머
        self.shift_dwell_timer = 0.0# DWELL: 변속 직후 다운시프트 금지 타이머

        # --- 실제 주행 상태 (물리) ---
        self.wheel_speed = 0.0     # -1(후진)..1(전진) 정규화된 바퀴 속도
        self.v_smooth = 0.0        # SMOOTH: 헌팅 방지를 위한 속도 스무딩 값
        self.gear = "P"            # "P", "R", "N", "D"
        self.axis = 0.0            # -50..50 원본 입력 값

        # --- 시뮬레이션 파라미터 로드 ---
        self._load_parameters()

    def _load_parameters(self):
        """config.py 파일로부터 시뮬레이션에 필요한 모든 상수를 불러옵니다."""
        self.RPM_MAX = float(getattr(config, "RPM_SCALE_MAX", 8000.0))
        self.RPM_IDLE = float(getattr(config, "RPM_IDLE_VALUE", 700.0)) / self.RPM_MAX
        self.RPM_CREEP = float(getattr(config, "RPM_CREEP_VALUE", 1100.0)) / self.RPM_MAX
        self.RPM_FUELCUT = float(getattr(config, "RPM_FUEL_CUT_VALUE", 7000.0)) / self.RPM_MAX
        self.RPM_R_MAX_R = float(getattr(config, "REVERSE_RPM_MAX_VALUE", 4000.0)) / self.RPM_MAX

        self.AXIS_DEADZONE = float(getattr(config, "AXIS_DEADZONE_UNITS", 5.0))
        self.SHIFT_DELAY = float(getattr(config, "SHIFT_DURATION_S", 0.25))
        self.ENGINE_INERTIA = float(getattr(config, "ENGINE_INERTIA", 0.28))
        self.SHIFT_HYST = float(getattr(config, "SHIFT_HYSTERESIS_PCT", 4.0))

        # 가속/감속 및 저항 계수
        self.A_POS = 0.2
        self.A_NEG = 0.3
        self.D0 = 0.030  # 정지마찰
        self.D1 = 0.10   # 선형저항
        self.D2 = 0.18   # 공기저항
        self.MASS_K = 2.0

        # 크리프(Creep) 현상 파라미터 (D 기어에서 브레이크를 뗐을 때 천천히 앞으로 가는 현상)
        self.CREEP_A = 0.05
        self.CREEP_CAP = 0.12 # 크리프 최대 속도 (12%)
        self.V_EPS = 0.01     # 정지로 간주하는 속도 경계

        # 스포츠 모드 파라미터
        self.SPORT_POS_SCALE = 1.6
        self.SHIFT_RPM_DROP = 0.08 # 업시프트 시 RPM 하락량
        self.SHIFT_RPM_POP = 0.12  # 다운시프트 시 RPM 상승량 (Rev-matching)

        # 가상 9단 변속 경계 (속도 %)
        self.SHIFT_BANDS = [8, 15, 25, 35, 50, 65, 80, 92]
        
        # 헌팅 방지 파라미터
        self.SHIFT_LOCK_S = max(0.15, self.SHIFT_DELAY)
        self.SHIFT_DWELL_S = 0.60
        self.DWELL_UP_EXTRA = 3.0
        self.SPEED_SMOOTH_TAU = 0.30

    # --------- Public API (main.py에서 호출) ---------
    def update(self, dt: float, inputs: dict):
        """메인 업데이트 함수. 매 tick마다 호출됩니다."""
        self._ingest_inputs(inputs)
        self._update_engine_state(dt)
        self._update_steering(dt, inputs)
        self._apply_gear_change(inputs)

        # 1. 입력값(-50..50)을 가속 명령(-1..1)으로 변환
        u = clamp(self.axis / 50.0, -1.0, 1.0)
        a_cmd = (self.A_POS * u) if u >= 0.0 else (-self.A_NEG * (-u))

        if self.sport_mode_on and u > 0:
            a_cmd *= self.SPORT_POS_SCALE

        # 2. 변속 연출 중에는 토크를 감소 (토크 컷)
        if self.shift_timer > 0.0:
            self.shift_timer = max(0.0, self.shift_timer - dt)
            k = 1.0 - (self.shift_timer / self.SHIFT_DELAY)
            a_cmd *= k

        # 3. 기어에 따른 물리적 제약 적용
        if self.gear in ("P", "N"):
            a_cmd = 0.0
            # P/N에서는 바퀴를 강제로 멈춤
            if abs(self.wheel_speed) > 0.0:
                self.wheel_speed -= math.copysign(min(abs(self.wheel_speed), 4.0 * dt), self.wheel_speed)
        elif self.gear == "R":
            a_cmd = -abs(a_cmd) # 후진 가속만 허용
        
        # 4. D 기어 데드존 및 크리프 처리
        if self.gear == "D" and abs(self.axis) < self.AXIS_DEADZONE:
            a_cmd = 0.0 # 데드존 내에서는 가속 명령 없음
            # 정지에 가까우면 크리프 현상 구현
            if abs(self.wheel_speed) < self.V_EPS:
                self.wheel_speed = clamp(self.wheel_speed + self.CREEP_A * dt, 0.0, self.CREEP_CAP)

        # 5. 물리 저항(드래그) 계산
        v = self.wheel_speed
        drag = (self.D0 * math.copysign(1, v)) + (self.D1 * v) + (self.D2 * v * abs(v))

        # 6. 최종 가속도를 계산하고 속도에 적분
        a = (a_cmd - drag) * self.MASS_K
        self.wheel_speed = clamp(self.wheel_speed + a * dt, -1.0, 1.0)
        
        # 7. 기어 방향과 반대 속도 방지
        if (self.gear == "D" and self.wheel_speed < 0.0) or \
           (self.gear == "R" and self.wheel_speed > 0.0):
            self.wheel_speed = 0.0

        # --- 시각 효과 업데이트 ---
        self._update_speed_smoothing(dt)
        self._update_virtual_gear_anti_hunting()
        self._update_virtual_rpm(dt, a_cmd)

    def get_state_snapshot(self) -> dict:
        """웹 클라이언트에 보낼 현재 상태 딕셔너리를 반환합니다."""
        return {
            "virtual_rpm": clamp(self.virtual_rpm, 0.0, 1.0),
            "speed_pct": int(abs(self.wheel_speed) * 100),
            "gear": self.gear,
            "virtual_gear": self.virtual_gear,
            "head_on": self.head_on,
            "engine_running": self.engine_running,
            "sport_mode_on": self.sport_mode_on,
        }

    def get_hardware_outputs(self) -> dict:
        """실제 하드웨어로 보낼 제어값 딕셔너리를 반환합니다."""
        braking = self.axis <= -self.AXIS_DEADZONE
        is_moving = self.gear in ('D', 'R')
        tail_brightness = 1.0 if (braking and is_moving) else (0.5 if self.head_on else 0.0)

        return {
            "steering_us": int(self.steer_cur_us),
            "esc_norm": self.wheel_speed,
            "head_brightness": 1.0 if self.head_on else 0.0,
            "tail_brightness": tail_brightness,
        }

    # --------- 내부 서브시스템 업데이트 함수 ---------
    def _ingest_inputs(self, inputs: dict):
        self.axis = clamp(float(inputs.get("axis", 0.0)), -50.0, 50.0)

    def _update_engine_state(self, dt: float):
        # 크랭킹(시동 거는 중) 타이머 처리
        if self.engine_cranking_timer > 0.0:
            self.engine_cranking_timer -= dt
            if self.engine_cranking_timer <= 0.0:
                self.engine_running = True
        
        # 엔진 상태에 따른 RPM 시각 효과
        if not self.engine_running:
            if self.engine_cranking_timer > 0.0: # 크랭킹 중에는 RPM 바늘 떨림
                self.virtual_rpm = clamp(0.03 + random.uniform(-0.02, 0.02), 0.0, 1.0)
            else:
                self.virtual_rpm = 0.0

    def _update_steering(self, dt: float, inputs: dict):
        allow_steer = bool(getattr(config, "ALLOW_STEER_WHEN_ENGINE_ON", True))
        steer_dir = 0
        if (allow_steer and self.engine_running) or (self.gear != "P"):
            steer_dir = int(inputs.get("steer_dir", 0))

        if steer_dir == -1: self.steer_target_us = config.STEER_LEFT_US
        elif steer_dir == 1: self.steer_target_us = config.STEER_RIGHT_US
        else: self.steer_target_us = config.STEER_CENTER_US
        
        # 조향 서보를 부드럽게 움직이도록 처리
        max_step = float(getattr(config, "STEER_SPEED_US_PER_S", 1000.0)) * dt
        d = self.steer_target_us - self.steer_cur_us
        self.steer_cur_us += clamp(d, -max_step, max_step)
        
    def _apply_gear_change(self, inputs: dict):
        new_gear = inputs.get("gear")
        if new_gear and new_gear != self.gear:
            # P, N으로는 언제든 변경 가능
            if new_gear in ("P", "N"):
                self.gear = new_gear
                self.wheel_speed = 0.0
                self._reset_shift_timers()
            # R, D는 현재 기어가 R,D이거나, 브레이크를 밟았을 때만 변경 가능
            elif new_gear in ("R", "D") and (self.gear in ("R", "D") or self.axis <= -self.AXIS_DEADZONE):
                is_direction_change = (self.gear in ('D','R') and self.gear != new_gear)
                self.gear = new_gear
                self.virtual_gear = 1 # R 기어는 항상 1단으로 표시
                self._reset_shift_timers()
                self.virtual_rpm = max(self.RPM_IDLE, self.virtual_rpm - self.SHIFT_RPM_DROP)
                if is_direction_change:
                  self.wheel_speed = 0.0 # 방향 전환 시 즉시 정지
            else:
                inputs["shift_fail"] = True

    def _reset_shift_timers(self):
        """기어 변경 시 변속 관련 타이머를 초기화합니다."""
        self.shift_timer = self.SHIFT_DELAY
        self.shift_lock_timer = self.SHIFT_LOCK_S
        self.shift_dwell_timer = self.SHIFT_DWELL_S
        
    def _update_speed_smoothing(self, dt: float):
        """(ANTI-HUNTING) 속도 값을 부드럽게 만들어 급격한 변속을 방지합니다."""
        sp_now = abs(self.wheel_speed) * 100.0
        alpha = clamp(dt / self.SPEED_SMOOTH_TAU, 0.0, 1.0)
        self.v_smooth = (1 - alpha) * self.v_smooth + alpha * sp_now

    def _update_virtual_gear_anti_hunting(self):
        """(ANTI-HUNTING) D 기어에서 속도에 맞춰 가상 기어를 계산합니다."""
        tick = config.TICK_S
        if self.shift_lock_timer > 0: self.shift_lock_timer -= tick
        if self.shift_dwell_timer > 0: self.shift_dwell_timer -= tick

        if self.gear != "D" or self.shift_lock_timer > 0: # D가 아니거나, LOCK 상태면 평가 안함
            return

        # 1. 현재 속도(v_smooth)에 맞는 목표 기어 계산
        target_gear = 1
        for i, up_threshold in enumerate(self.SHIFT_BANDS, start=1):
            if self.v_smooth >= up_threshold:
                target_gear = i + 1
        
        cur_gear = self.virtual_gear
        if target_gear == cur_gear: return

        # 2. 다운시프트 조건 검사
        if target_gear < cur_gear:
            # DWELL: 변속 직후엔 다운시프트 금지
            if self.shift_dwell_timer > 0: return
            # HYSTERESIS: 속도가 이전 기어의 변속점 - 히스테리시스 값보다 낮아져야만 다운시프트 허용
            down_threshold = self.SHIFT_BANDS[cur_gear - 2] - self.SHIFT_HYST if cur_gear >= 2 else 0
            if self.v_smooth >= down_threshold: return
        
        # 3. 업시프트 조건 검사
        elif target_gear > cur_gear and self.shift_dwell_timer > 0:
            # DWELL 중에는 더 높은 속도에서만 업시프트 허용
            up_threshold = self.SHIFT_BANDS[cur_gear - 1] + self.DWELL_UP_EXTRA if cur_gear -1 < len(self.SHIFT_BANDS) else 1000
            if self.v_smooth < up_threshold: return
            
        # 4. 변속 확정 및 시각 효과 적용
        is_upshift = target_gear > self.virtual_gear
        self.virtual_gear = target_gear
        self._reset_shift_timers()

        if is_upshift: # 업시프트: RPM 하락
            self.virtual_rpm = max(self.RPM_IDLE, self.virtual_rpm - self.SHIFT_RPM_DROP)
        else: # 다운시프트: RPM 팝 (Rev-matching)
            self.virtual_rpm = clamp(self.virtual_rpm + self.SHIFT_RPM_POP, 0.0, self.RPM_FUELCUT)

    def _update_virtual_rpm(self, dt: float, a_cmd: float):
        """가속/감속 및 속도에 따라 가상 RPM을 계산합니다."""
        if not self.engine_running: return
        
        v_abs = abs(self.wheel_speed)
        
        # 기본 RPM은 속도에 비례, 기어에 따라 최소값(IDLE/CREEP) 설정
        base_rpm = self.RPM_IDLE
        if self.gear in ("D", "R"):
            base_rpm = lerp(self.RPM_CREEP, self.RPM_FUELCUT, v_abs)
        
        # 가속 명령에 따라 목표 RPM을 조절
        slew_rate = 0.5 if a_cmd > 0 else 0.8
        target_rpm = max(base_rpm, v_abs * self.RPM_FUELCUT * (1 + a_cmd * slew_rate))
        
        # 관성을 적용하여 현재 RPM을 목표 RPM으로 부드럽게 이동
        alpha = clamp(dt / self.ENGINE_INERTIA, 0.0, 1.0)
        self.virtual_rpm = lerp(self.virtual_rpm, target_rpm, alpha)
        
        # 기어에 따른 RPM 상한 적용
        rpm_limit = self.RPM_R_MAX_R if self.gear == "R" else self.RPM_FUELCUT
        self.virtual_rpm = clamp(self.virtual_rpm, self.RPM_IDLE, rpm_limit)