from adafruit_servokit import ServoKit
import time


# ===== 하드웨어 설정 상수 =====
# Axis 범위
AXIS_MIN = -50
AXIS_MAX = 50

# 조향 범위
STEER_MIN = -66
STEER_MAX = 66

# 서보 PWM 펄스 범위
SERVO_PULSE_MIN = 1700
SERVO_PULSE_MAX = 2200

# 채널 매핑
STEER_CHANNEL = 0  # 조향 서보
ESC_CHANNEL = 1    # ESC
LED_CHANNEL = 2    # 전조등 LED

# ServoKit 초기화
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정


def init_hardware() -> None:
    # 조향: 서보 129°를 중립으로 사용, ESC: 120° 중립, LED: 꺼진 상태
    set_steer_angle(0)
    set_throttle(120)
    set_led(False)  # LED 초기화 시 꺼진 상태로 설정

def set_steer_angle(steer_deg_minus90_to_90: int) -> None:
    """
    차량 조향 입력(-90..+90)을 서보 각도로 변환.
    - 서보 129° = 중립
    - 왼쪽 한계 60°, 오른쪽 한계 180°
    - 음수/양수 구간에 대해 비대칭 선형 매핑
    """
    CENTER = 129
    LEFT_LIMIT = 60
    RIGHT_LIMIT = 180

    s = max(-66, min(66, int(steer_deg_minus90_to_90)))
    if s >= 0:
        # 0..+90  -> 120..RIGHT_LIMIT 선형
        servo_angle = CENTER + (RIGHT_LIMIT - CENTER) * (s / 90)
    else:
        # -90..0 -> LEFT_LIMIT..120 선형
        servo_angle = CENTER + (CENTER - LEFT_LIMIT) * (s / 90)
    kit.servo[STEER_CHANNEL].angle = int(max(0, min(180, round(servo_angle))))

def set_throttle(angle):
    pulse_width = int(1000 + (angle / 180) * 1198)  # 0°=1000μs, 90°≈1599μs, 180°≈2198μs
    kit.servo[ESC_CHANNEL].angle = angle
    return pulse_width

def set_led(on: bool) -> None:
    """
    전조등 LED 제어
    - on=True: LED 켜기 (PWM duty cycle 100%)
    - on=False: LED 끄기 (PWM duty cycle 0%)
    """
    if on:
        # LED 켜기 - PWM duty cycle 100% (4095/4095)
        kit._pca.channels[LED_CHANNEL].duty_cycle = 4095
    else:
        # LED 완전히 끄기 - PWM duty cycle 0% 
        kit._pca.channels[LED_CHANNEL].duty_cycle = 0

def arm_esc_sequence() -> None:
    set_throttle(120)

