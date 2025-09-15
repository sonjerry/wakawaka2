import time
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정

# 채널 번호
STEER_CHANNEL = 0  # 조향 서보
ESC_CHANNEL = 1    # ESC

# 펄스 폭을 angle로 선형 매핑 (0° = 1000μs, 90° = 1599μs, 180° = 2198μs)
def set_throttle(angle):
    pulse_width = int(1000 + (angle / 180) * 1198)  # 0°=1000μs, 90°≈1599μs, 180°≈2198μs
    kit.servo[ESC_CHANNEL].angle = angle
    print(f"Throttle set to {angle}° (calculated {pulse_width}μs)")
    return pulse_width

# 조향 각도 설정 (-90..+90 입력 → 서보 각도 매핑)
def set_steer_angle(steer_deg_minus90_to_90: int) -> int:
    """
    - 논리 조향 입력(-90..+90)을 서보 각도로 변환하여 설정
    - 서보 129° ≈ 중립, 좌 60° 근처, 우 180° 근처로 선형 매핑
    - 반환값: 실제 설정된 서보 각도(정수)
    """
    CENTER = 129
    LEFT_LIMIT = 60
    RIGHT_LIMIT = 180

    s = max(-90, min(90, int(steer_deg_minus90_to_90)))
    if s >= 0:
        servo_angle = CENTER + (RIGHT_LIMIT - CENTER) * (s / 90)
    else:
        servo_angle = CENTER + (CENTER - LEFT_LIMIT) * (s / 90)
    servo_angle_i = int(max(0, min(180, round(servo_angle))))
    kit.servo[STEER_CHANNEL].angle = servo_angle_i
    print(f"Steer cmd {s}° -> servo {servo_angle_i}° (L{LEFT_LIMIT}/C{CENTER}/R{RIGHT_LIMIT})")
    return servo_angle_i

# 메인 로직
try:
    # 1. Arming 시퀀스
    print("Arming 시작...")
    set_throttle(90)  # 1599μs 1초 유지
    time.sleep(1)
    set_throttle(120)  # 약 1732μs 1초 유지
    time.sleep(1)
    set_throttle(90)  # 중립 복귀
    # 스티어링 초기 중앙
    set_steer_angle(0)
    print("Arming 완료. w/s=쓰로틀, a/d=조향, c=조향 중앙, q=종료.")

    # 2. 입력으로 각도 조절
    current_angle = 90
    current_steer = 0  # -90..+90
    while True:
        command = input("명령 입력 (w:쓰로틀+, s:쓰로틀-, a:좌, d:우, c:중앙, q:종료): ").lower()
        if command == 'w':
            current_angle = min(current_angle + 5, 180)
            set_throttle(current_angle)
        elif command == 's':
            current_angle = max(current_angle - 5, 0)
            set_throttle(current_angle)
        elif command == 'a':
            current_steer = max(current_steer - 5, -90)
            set_steer_angle(current_steer)
        elif command == 'd':
            current_steer = min(current_steer + 5, 90)
            set_steer_angle(current_steer)
        elif command == 'c':
            current_steer = 0
            set_steer_angle(current_steer)
        elif command == 'q':
            break
        else:
            print("잘못된 입력. w/s/a/d/c/q 중 선택하세요.")

    # 마무리: 중립 복귀
    set_throttle(120)
    set_steer_angle(0)
    print("프로그램 종료. 중립으로 설정.")

except KeyboardInterrupt:
    pass
finally:
    set_throttle(120)  # 안전 중립 복귀
    set_steer_angle(0)
    print("프로그램 강제 종료. 중립으로 설정.")