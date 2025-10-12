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
SERVO_PULSE_MIN = 1599 
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
    """
    ESC PWM 매핑:
    - 65도 (후진 최대): 1600μs
    - 120도 (중립): 1800μs
    - 130도 (크리핑): 1875μs
    - 180도 (전진 최대): 2200μs
    - 아밍: 1599μs, 1799μs
    """
    angle = max(65, min(180, angle))
    
    if angle < 120:
        # 후진 영역: 65-120도 -> 1600-1800μs
        pulse_width = int(1600 + (angle - 65) / (120 - 65) * (1800 - 1600))
    elif angle < 130:
        # 크리핑 영역: 120-130도 -> 1800-1875μs
        pulse_width = int(1800 + (angle - 120) / (130 - 120) * (1875 - 1800))
    else:
        # 전진 영역: 130-180도 -> 1875-2200μs
        pulse_width = int(1875 + (angle - 130) / (180 - 130) * (2200 - 1875))
    
    kit.servo[ESC_CHANNEL].set_pulse_width_range(pulse_width, pulse_width)
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
    """ESC 아밍 시퀀스: 1599μs, 1799μs"""
    # 1599μs
    kit.servo[ESC_CHANNEL].set_pulse_width_range(1599, 1599)
    time.sleep(0.5)
    # 1799μs
    kit.servo[ESC_CHANNEL].set_pulse_width_range(1799, 1799)
    time.sleep(0.5)
    # 중립 (1800μs)
    set_throttle(120)

