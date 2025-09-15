from adafruit_servokit import ServoKit
import time


# 채널 매핑
STEER_CHANNEL = 0  # 조향 서보
ESC_CHANNEL = 1    # ESC

# ServoKit 초기화
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정


def init_hardware() -> None:
    # 조향: 서보 120°를 중립으로 사용, ESC: 120° 중립
    set_steer_angle(110)
    set_throttle(120)

def set_steer_angle(steer_deg_minus90_to_90: int) -> None:
    """
    차량 조향 입력(-90..+90)을 서보 각도로 변환.
    - 서보 120° = 중립
    - 왼쪽 한계 60°, 오른쪽 한계 180°
    - 음수/양수 구간에 대해 비대칭 선형 매핑
    """
    CENTER = 110
    LEFT_LIMIT = 60
    RIGHT_LIMIT = 180

    s = max(-90, min(90, int(steer_deg_minus90_to_90)))
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

def arm_esc_sequence() -> None:
    # Arming: 90°(~1599µs) 1s → 120°(중립, ~1732µs) 1s
    set_throttle(90)
    time.sleep(0.5)
    set_throttle(120)
    time.sleep(0.5)
    set_throttle(120)
    

