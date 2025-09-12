# hardware.py
# Raspberry Pi 5 PWM/Servo/LED controller for WakaWaka
# Channels: 0=Steer Servo, 1=ESC, 2=Headlight LED, 3=Taillight LED
# Drop-in for main.py (methods/signatures match main.py usage).

from __future__ import annotations
import time
import logging

try:
    import pigpio  # precise servo PWM on Raspberry Pi
    _HAS_PIGPIO = True
except Exception:
    pigpio = None
    _HAS_PIGPIO = False

logger = logging.getLogger(__name__)


class PWMController:
    """
    Public API expected by main.py:
      - arm_esc()
      - set_servo_angle(angle_deg: float)     # -90..+90 (A/D 키)
      - set_esc_speed(speed_pct: float)       # -100..+100 (W/S 키 → axis)
      - set_headlight(on: bool)
      - emergency_stop()
      - cleanup()

    추가(선택):
      - set_gear(gear: str)  # 'P','R','N','D'
      - set_taillight(on: bool)
    """

    # ===== GPIO 핀 매핑 (필요시 여기만 바꾸면 됨) =====
    # Pi5 하드웨어 PWM 가능한 핀: 12, 13, 18, 19
    GPIO_MAP = {
        0: 12,  # Servo (steer)
        1: 13,  # ESC (drive)
        2: 18,  # Headlight LED
        3: 19,  # Taillight LED
    }

    # ===== 펄스/서보 설정 =====
    PULSE_MIN = 1000  # µs
    PULSE_MAX = 2000  # µs
    PULSE_NEU = 1500  # µs
    SERVO_MIN = 1000  # µs at -90°
    SERVO_MAX = 2000  # µs at +90°

    # LED를 단순 ON/OFF로 쓸지, PWM 밝기 제어를 쓸지
    LED_USE_PWM = False  # True면 PWM 밝기 제어

    def __init__(self) -> None:
        self.pi = None
        self._armed = False
        self._gear = 'P'  # 안전 기본값

        if _HAS_PIGPIO:
            try:
                self.pi = pigpio.pi()
                if not self.pi.connected:
                    raise RuntimeError("pigpio daemon not connected")
                logger.info("pigpio connected.")
                self._setup_outputs()

                # 안전 초기화
                self._apply_servo_pulse(self.PULSE_NEU)
                self._apply_esc_pulse(self.PULSE_NEU)
                self._set_led(self.GPIO_MAP[2], False)  # head off
                self._set_led(self.GPIO_MAP[3], True)   # tail parking on (선호에 맞게 조정)
            except Exception as e:
                logger.error(f"pigpio init failed: {e}. Using dummy fallback.")
                self._fallback_init()
        else:
            self._fallback_init()

    # ========== Public API (main.py가 직접 호출) ==========

    def arm_esc(self) -> None:
        """ESC 시동 준비: 중립 펄스로 안정화."""
        logger.info("Arming ESC...")
        self._apply_esc_pulse(self.PULSE_NEU)
        time.sleep(1.0)
        self._armed = True
        logger.info("ESC armed (neutral).")

    def set_servo_angle(self, angle_deg: float) -> None:
        """-90..+90도를 1000..2000µs로 선형 매핑."""
        angle = max(-90.0, min(90.0, float(angle_deg)))
        span = self.SERVO_MAX - self.SERVO_MIN
        pulse = int(self.SERVO_MIN + (angle + 90.0) / 180.0 * span)
        logger.debug(f"Servo {angle_deg:.1f}° -> {pulse}us")
        self._apply_servo_pulse(pulse)

    def set_esc_speed(self, speed_pct: float) -> None:
        """
        입력: -100..+100 (axis 기반: +가속, -브레이크).
        기어 규칙 (내연기관 흐름 반영):
          - P/N : 항상 1500µs 유지 (토크 없음)
          - D   : axis>0만 가속, 1500..2000µs / axis<=0은 감속 → 1500µs
          - R   : axis>0만 가속, 1500..1000µs / axis<=0은 감속 → 1500µs
        """
        v = float(speed_pct)
        g = self._gear

        if not self._armed or g in ('P', 'N'):
            pulse = self.PULSE_NEU
        elif g == 'D':
            if v > 0:
                pulse = self._map_forward(v)    # 0..100 → 1500..2000
            else:
                pulse = self.PULSE_NEU          # 브레이크 → 역토크/후진 금지
        elif g == 'R':
            if v > 0:
                pulse = self._map_reverse(v)    # 0..100 → 1500..1000
            else:
                pulse = self.PULSE_NEU          # 브레이크 → 전진 금지
        else:
            pulse = self.PULSE_NEU

        logger.debug(f"ESC cmd {speed_pct:.1f}% in {g} -> {pulse}us")
        self._apply_esc_pulse(pulse)

        # 선택: 브레이크/후진 시 테일라이트 힌트
        try:
            braking = (g == 'D' and v <= 0) or (g == 'R' and v <= 0)
            self._set_taillight_brightness(100 if braking else 40)
        except Exception:
            pass

    def set_headlight(self, on: bool) -> None:
        self._set_led(self.GPIO_MAP[2], bool(on))

    def emergency_stop(self) -> None:
        """즉시 중립/안전 상태."""
        logger.warning("EMERGENCY STOP!")
        self._apply_esc_pulse(self.PULSE_NEU)
        self._apply_servo_pulse(self.PULSE_NEU)
        self._set_led(self.GPIO_MAP[2], False)  # head off
        self._set_led(self.GPIO_MAP[3], True)   # tail parking on
        self._armed = False

    def cleanup(self) -> None:
        logger.info("PWMController cleanup.")
        if self.pi:
            try:
                self._apply_esc_pulse(self.PULSE_NEU)
                self._apply_servo_pulse(self.PULSE_NEU)
                self._set_led(self.GPIO_MAP[2], False)
                self._set_led(self.GPIO_MAP[3], False)
            finally:
                self.pi.stop()
                self.pi = None

    # ========== Optional: 기어 전달 API (권장) ==========

    def set_gear(self, gear: str) -> None:
        g = (gear or '').upper()
        if g not in ('P', 'R', 'N', 'D'):
            logger.warning(f"Ignoring invalid gear '{gear}'")
            return
        logger.info(f"Gear -> {g}")
        self._gear = g
        # P/N 전환 시 즉시 중립으로 안전화
        if g in ('P', 'N'):
            self._apply_esc_pulse(self.PULSE_NEU)

    def set_taillight(self, on: bool) -> None:
        self._set_led(self.GPIO_MAP[3], bool(on))

    # ========== 내부 헬퍼 ==========

    def _setup_outputs(self) -> None:
        self.pi.set_mode(self.GPIO_MAP[0], pigpio.OUTPUT)
        self.pi.set_mode(self.GPIO_MAP[1], pigpio.OUTPUT)
        self.pi.set_mode(self.GPIO_MAP[2], pigpio.OUTPUT)
        self.pi.set_mode(self.GPIO_MAP[3], pigpio.OUTPUT)

    def _apply_servo_pulse(self, pulse_us: int) -> None:
        if self.pi:
            self.pi.set_servo_pulsewidth(self.GPIO_MAP[0], int(pulse_us))
        else:
            logger.debug(f"[dummy] servo -> {pulse_us}us")

    def _apply_esc_pulse(self, pulse_us: int) -> None:
        if self.pi:
            self.pi.set_servo_pulsewidth(self.GPIO_MAP[1], int(pulse_us))
        else:
            logger.debug(f"[dummy] esc -> {pulse_us}us")

    def _set_led(self, gpio: int, on: bool) -> None:
        if self.pi:
            if self.LED_USE_PWM:
                duty = 255 if on else 0
                self.pi.set_PWM_dutycycle(gpio, duty)
            else:
                self.pi.write(gpio, 1 if on else 0)
        else:
            logger.debug(f"[dummy] gpio {gpio} -> {'ON' if on else 'OFF'}")

    def _set_taillight_brightness(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        gpio = self.GPIO_MAP[3]
        if self.pi and self.LED_USE_PWM:
            duty = int(255 * (percent / 100.0))
            self.pi.set_PWM_dutycycle(gpio, duty)
        else:
            # PWM 안 쓰면 50% 기준으로 ON/OFF
            self._set_led(gpio, percent >= 50)

    def _map_forward(self, v_pct: float) -> int:
        # 0..100 → 1500..2000µs
        v = max(0.0, min(100.0, v_pct))
        return int(self.PULSE_NEU + (v / 100.0) * (self.PULSE_MAX - self.PULSE_NEU))

    def _map_reverse(self, v_pct: float) -> int:
        # 0..100 → 1500..1000µs (후진)
        v = max(0.0, min(100.0, v_pct))
        return int(self.PULSE_NEU - (v / 100.0) * (self.PULSE_NEU - self.PULSE_MIN))

    def _fallback_init(self) -> None:
        self.pi = None
        logger.warning("pigpio not available; running in dummy mode (no hardware driven).")
