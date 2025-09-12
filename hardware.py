# hardware.py — PCA9685 external PWM driver (drop-in for main.py)
# Channels: 0=Steer Servo, 1=ESC, 2=Headlight, 3=Taillight
from __future__ import annotations
import time
import logging

logger = logging.getLogger(__name__)

# ---- Try PCA9685 first (no pigpio / no pigpiod needed) ----
_HAS_PCA9685 = False
try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    _HAS_PCA9685 = True
except Exception as e:
    logger.warning(f"PCA9685 import failed: {e}")

# (optional) last-resort dummy fallback
class _DummyPCA:
    def __init__(self): pass
    def deinit(self): pass
    @property
    def channels(self):
        class _C:
            duty_cycle = 0
        return [ _C() for _ in range(16) ]
    @property
    def frequency(self): return 50
    @frequency.setter
    def frequency(self, v): pass

class PWMController:
    """
    Public API expected by main.py:
      - arm_esc()
      - set_servo_angle(angle_deg: float)     # -90..+90 (A/D)
      - set_esc_speed(speed_pct: float)       # -100..+100 (W/S -> axis)
      - set_headlight(on: bool)
      - emergency_stop()
      - cleanup()
      - set_gear(gear: str)  # 'P','R','N','D' (optional but used)
      - set_taillight(on: bool)
    """

    # ===== PCA9685 channel mapping =====
    CH_STEER = 0
    CH_ESC = 1
    CH_HEAD = 2
    CH_TAIL = 3

    # ===== pulse settings =====
    PULSE_MIN = 1000  # us
    PULSE_MAX = 2000  # us
    PULSE_NEU = 1500  # us
    SERVO_MIN = 1000  # us at -90°
    SERVO_MAX = 2000  # us at +90°

    # LEDs: ON/OFF 기본. (PCA9685는 채널 전체 주파수 공유 → 중간 밝기는 50Hz에서 깜빡임 생길 수 있음)
    LED_USE_PWM = False

    # I2C addr (보통 0x40). 필요하면 환경변수/설정으로 바꾸세요.
    PCA9685_ADDR = 0x40
    PCA9685_FREQ = 50  # 50Hz (서보/ESC)

    def __init__(self) -> None:
        self._gear = 'P'
        self._armed = False
        self._pca = None

        if _HAS_PCA9685:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self._pca = PCA9685(i2c, address=self.PCA9685_ADDR)
                self._pca.frequency = self.PCA9685_FREQ
                logger.info(f"PCA9685 connected at 0x{self.PCA9685_ADDR:02X}, {self.PCA9685_FREQ}Hz")

                # safe init
                self._apply_servo_pulse(self.PULSE_NEU)
                self._apply_esc_pulse(self.PULSE_NEU)
                self._set_led(self.CH_HEAD, False)  # head off
                self._set_led(self.CH_TAIL, True)   # tail parking on
            except Exception as e:
                logger.error(f"PCA9685 init failed: {e}. Using dummy fallback.")
                self._pca = _DummyPCA()
        else:
            logger.warning("PCA9685 library unavailable; using dummy (no hardware driven).")
            self._pca = _DummyPCA()

    # ========= public API =========
    def arm_esc(self) -> None:
        logger.info("Arming ESC (neutral hold)...")
        self._apply_esc_pulse(self.PULSE_NEU)
        time.sleep(1.0)
        self._armed = True
        logger.info("ESC armed.")

    def set_servo_angle(self, angle_deg: float) -> None:
        angle = max(-90.0, min(90.0, float(angle_deg)))
        span = self.SERVO_MAX - self.SERVO_MIN
        pulse = int(self.SERVO_MIN + (angle + 90.0) / 180.0 * span)
        self._apply_servo_pulse(pulse)

    def set_esc_speed(self, speed_pct: float) -> None:
        """
        speed_pct: -100..+100, but gear rules restrict direction:
          - P/N : always neutral
          - D   : v>0 → 1500..2000us, v<=0 → 1500us (no reverse)
          - R   : v>0 → 1500..1000us, v<=0 → 1500us (no forward)
        """
        v = float(speed_pct)
        g = self._gear

        if not self._armed or g in ('P', 'N'):
            pulse = self.PULSE_NEU
        elif g == 'D':
            pulse = self._map_forward(v) if v > 0 else self.PULSE_NEU
        elif g == 'R':
            pulse = self._map_reverse(v) if v > 0 else self.PULSE_NEU
        else:
            pulse = self.PULSE_NEU

        self._apply_esc_pulse(pulse)

        # brake/neutral hint on tail
        try:
            braking = (g == 'D' and v <= 0) or (g == 'R' and v <= 0)
            self._set_taillight_brightness(100 if braking else 40)
        except Exception:
            pass

    def set_headlight(self, on: bool) -> None:
        self._set_led(self.CH_HEAD, bool(on))

    def set_taillight(self, on: bool) -> None:
        self._set_led(self.CH_TAIL, bool(on))

    def emergency_stop(self) -> None:
        logger.warning("EMERGENCY STOP!")
        self._apply_esc_pulse(self.PULSE_NEU)
        self._apply_servo_pulse(self.PULSE_NEU)
        self._set_led(self.CH_HEAD, False)
        self._set_led(self.CH_TAIL, True)
        self._armed = False

    def cleanup(self) -> None:
        logger.info("PWMController cleanup.")
        try:
            self._apply_esc_pulse(self.PULSE_NEU)
            self._apply_servo_pulse(self.PULSE_NEU)
            self._set_led(self.CH_HEAD, False)
            self._set_led(self.CH_TAIL, False)
        finally:
            try:
                if self._pca and hasattr(self._pca, "deinit"):
                    self._pca.deinit()
            except Exception:
                pass

    def set_gear(self, gear: str) -> None:
        g = (gear or '').upper()
        if g not in ('P', 'R', 'N', 'D'):
            logger.warning(f"Ignoring invalid gear '{gear}'")
            return
        logger.info(f"Gear -> {g}")
        self._gear = g
        if g in ('P', 'N'):
            self._apply_esc_pulse(self.PULSE_NEU)

    # ========= helpers =========
    def _period_us(self) -> float:
        return 1_000_000.0 / float(self.PCA9685_FREQ)  # ~20000us at 50Hz

    def _us_to_duty(self, pulse_us: int) -> int:
        # Adafruit lib uses 16-bit duty_cycle (0..65535)
        period = self._period_us()
        duty = int(max(0, min(65535, round((pulse_us / period) * 65535))))
        return duty

    def _apply_servo_pulse(self, pulse_us: int) -> None:
        duty = self._us_to_duty(int(pulse_us))
        self._pca.channels[self.CH_STEER].duty_cycle = duty

    def _apply_esc_pulse(self, pulse_us: int) -> None:
        duty = self._us_to_duty(int(pulse_us))
        self._pca.channels[self.CH_ESC].duty_cycle = duty

    def _set_led(self, ch: int, on: bool) -> None:
        if self.LED_USE_PWM:
            self._pca.channels[ch].duty_cycle = 65535 if on else 0
        else:
            # ON=100% (no flicker), OFF=0%
            self._pca.channels[ch].duty_cycle = 65535 if on else 0

    def _set_taillight_brightness(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        if self.LED_USE_PWM:
            duty = int(round(65535 * (percent / 100.0)))
            self._pca.channels[self.CH_TAIL].duty_cycle = duty
        else:
            self._set_led(self.CH_TAIL, percent >= 50)

    def _map_forward(self, v_pct: float) -> int:
        v = max(0.0, min(100.0, v_pct))
        return int(self.PULSE_NEU + (v / 100.0) * (self.PULSE_MAX - self.PULSE_NEU))

    def _map_reverse(self, v_pct: float) -> int:
        v = max(0.0, min(100.0, v_pct))
        return int(self.PULSE_NEU - (v / 100.0) * (self.PULSE_NEU - self.PULSE_MIN))
