# automission.py
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

# --- 가상 변속기 클래스 ---
class VirtualTransmission:
    """
    vRPM을 받아서 ESC 신호를 생성하는 가상 변속기 시스템.
    - vRPM 입력을 받아서 적절한 기어비를 적용
    - 8단 자동 변속기 시뮬레이션
    - 변속 상태기계를 통한 부드러운 변속
    - 최종적으로 ESC 신호(-1..1)를 출력
    """
    
    def __init__(self):
        # --- 기본 상태 ---
        self.engine_running = False
        self.esc_armed = False
        self.gear = "P"  # "P", "R", "N", "D"
        self.virtual_gear = 1  # 1..8단 (D 기어에서만 사용)
        
        # --- vRPM 입력 ---
        self.input_vrpm = 0.0  # 하드웨어에서 받은 vRPM 값
        
        # --- 변속 상태기계 ---
        self.shift_state = ShiftState.READY
        self.shift_timer = 0.0  # 현재 변속 단계 타이머 (ms)
        self.shift_direction = 0  # 1: 업시프트, -1: 다운시프트
        self.shift_target_gear = 1  # 변속 목표 기어
        
        # --- 출력 ---
        self.esc_output = 0.0  # 최종 ESC 출력 (-1..1)
        self.current_speed = 0.0  # 현재 속도 (0..1)
        
        # --- 파라미터 로드 ---
        self._load_parameters()

    def _load_parameters(self):
        """config.py에서 파라미터를 로드합니다."""
        # 기어비 및 토크 스케일
        self.gear_ratios = config.GEAR_RATIOS
        self.final_drive = config.FINAL_DRIVE
        
        # vRPM 설정
        self.vrpm_idle = config.VRPM_IDLE
        self.vrpm_red = config.VRPM_RED
        self.vrpm_up_threshold = config.VRPM_UP_THRESHOLD
        self.vrpm_down_threshold = config.VRPM_DOWN_THRESHOLD
        
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
        
        # 물리 파라미터
        self.wheel_radius = config.WHEEL_RADIUS
        self.rpm_scale_max = config.RPM_SCALE_MAX

    # --------- Public API ---------
    def update(self, dt: float, vrpm_input: float, gear_input: str = None):
        """
        가상 변속기를 업데이트합니다.
        dt: 델타 타임 (초)
        vrpm_input: 하드웨어에서 받은 vRPM 값
        gear_input: 기어 변경 입력 ("P", "R", "N", "D")
        """
        # vRPM 입력 업데이트
        self.input_vrpm = vrpm_input
        
        # 기어 변경 처리
        if gear_input and gear_input != self.gear:
            self._apply_gear_change(gear_input)
        
        # 변속기 로직 업데이트
        self._update_transmission_logic(dt)
        
        # ESC 출력 계산
        self._calculate_esc_output()

    def get_esc_output(self) -> float:
        """최종 ESC 출력값을 반환합니다 (-1..1)."""
        return self.esc_output

    def get_current_speed(self) -> float:
        """현재 속도를 반환합니다 (0..1)."""
        return self.current_speed

    def get_state_snapshot(self) -> dict:
        """현재 상태를 딕셔너리로 반환합니다."""
        return {
            "gear": self.gear,
            "virtual_gear": self.virtual_gear if self.gear == "D" else 1,
            "input_vrpm": self.input_vrpm,
            "esc_output": self.esc_output,
            "current_speed": self.current_speed,
            "shift_state": self.shift_state.value if self.gear == "D" else "READY",
            "engine_running": self.engine_running,
            "esc_armed": self.esc_armed,
        }

    # --------- 내부 메서드 ---------
    def _apply_gear_change(self, new_gear: str):
        """기어 변경을 처리합니다."""
        if new_gear in ("P", "N"):
            self.gear = new_gear
            self.current_speed = 0.0
            self._reset_shift_state()
        elif new_gear in ("R", "D"):
            self.gear = new_gear
            if new_gear == "D":
                self.virtual_gear = 1
            self._reset_shift_state()

    def _reset_shift_state(self):
        """변속 상태를 초기화합니다."""
        self.shift_state = ShiftState.READY
        self.shift_timer = 0.0
        self.shift_direction = 0
        self.shift_target_gear = self.virtual_gear

    def _update_transmission_logic(self, dt: float):
        """변속기 로직을 업데이트합니다."""
        if not self.engine_running or not self.esc_armed:
            self.esc_output = 0.0
            self.current_speed = 0.0
            return
        
        # D 기어에서만 변속 스케줄링
        if self.gear == "D":
            self._update_shift_scheduling()
            self._update_shift_state_machine(dt)
        
        # 속도 계산 (vRPM → 속도)
        self._calculate_speed_from_vrpm()

    def _update_shift_scheduling(self):
        """vRPM 기반 자동 변속 스케줄링을 처리합니다."""
        if self.shift_state != ShiftState.READY:
            return  # 변속 중이면 스케줄링 안함
        
        if self.input_vrpm < self.vrpm_idle:
            return  # RPM이 IDLE 이하면 변속 안함
        
        # 업시프트 체크
        if (self.virtual_gear < 8 and 
            self.input_vrpm >= self.vrpm_up_threshold):
            self._request_shift(1)  # 업시프트
            return
        
        # 다운시프트 체크
        if (self.virtual_gear > 1 and 
            self.input_vrpm <= self.vrpm_down_threshold):
            
            # 안전 검사: 다음 기어에서 레드라인 초과하지 않는지
            next_gear = self.virtual_gear - 1
            if next_gear >= 1:
                next_ratio = self.gear_ratios[next_gear - 1]
                current_ratio = self.gear_ratios[self.virtual_gear - 1]
                expected_vrpm = self.input_vrpm * (next_ratio / current_ratio)
                
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

    def _calculate_speed_from_vrpm(self):
        """vRPM에서 속도를 계산합니다."""
        if not self.engine_running:
            self.current_speed = 0.0
            return
        
        # vRPM을 바퀴 각속도로 변환 (기어비 적용)
        if self.gear == "D" and 1 <= self.virtual_gear <= 8:
            # D 기어: 8단 변속기 기어비 적용
            gear_ratio = self.gear_ratios[self.virtual_gear - 1]
            total_ratio = gear_ratio * self.final_drive
            wheel_rad_s = self.input_vrpm * (2.0 * math.pi / 60.0) / total_ratio
        elif self.gear == "R":
            # R 기어: 고정 기어비 (3.0) 적용
            wheel_rad_s = self.input_vrpm * (2.0 * math.pi / 60.0) / 3.0
        else:
            # P, N 기어: 정지
            self.current_speed = 0.0
            return
        
        # 바퀴 각속도를 속도로 변환
        speed_mps = wheel_rad_s * self.wheel_radius
        self.current_speed = clamp(speed_mps / 10.0, 0.0, 1.0)  # 0..1로 정규화

    def _calculate_esc_output(self):
        """최종 ESC 출력을 계산합니다."""
        if not self.engine_running or not self.esc_armed:
            self.esc_output = 0.0
            return
        
        # 기어에 따라 ESC 출력 결정
        if self.gear == "D":
            # D단: 전진 (0~1 속도 → 0~1 정규화값, 양수)
            self.esc_output = self.current_speed
        elif self.gear == "R":
            # R단: 후진 (0~1 속도 → -1~0 정규화값, 음수)
            self.esc_output = -self.current_speed
        else:
            # P, N단: 0.0 (중립)
            self.esc_output = 0.0

    def set_engine_state(self, running: bool, armed: bool = None):
        """엔진 상태를 설정합니다."""
        self.engine_running = running
        if armed is not None:
            self.esc_armed = armed
        elif not running:
            self.esc_armed = False

    def get_gear_info(self) -> dict:
        """기어 정보를 반환합니다."""
        return {
            "gear": self.gear,
            "virtual_gear": self.virtual_gear if self.gear == "D" else 1,
            "shift_state": self.shift_state.value,
            "shift_timer": self.shift_timer,
            "shift_direction": self.shift_direction,
            "shift_target_gear": self.shift_target_gear,
        }