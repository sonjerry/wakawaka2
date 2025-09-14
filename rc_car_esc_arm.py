import time
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정

# ESC 채널 번호 (예: 1번)
esc_channel = 1

# 펄스 폭을 angle로 선형 매핑 (0° = 1000μs, 90° = 1599μs, 180° = 2198μs)
def set_throttle(angle):
    pulse_width = int(1000 + (angle / 180) * 1198)  # 0°=1000μs, 90°≈1599μs, 180°≈2198μs
    kit.servo[esc_channel].angle = angle
    print(f"Throttle set to {angle}° (calculated {pulse_width}μs)")
    return pulse_width

# 메인 로직
try:
    # 1. Arming 시퀀스
    print("Arming 시작...")
    set_throttle(90)  # 1599μs 1초 유지
    time.sleep(1)
    set_throttle(120)  # 약 1732μs 1초 유지
    time.sleep(1)
    set_throttle(90)  # 중립 복귀
    print("Arming 완료. w를 입력해 각도를 올리고, s를 입력해 내리세요. q로 종료.")

    # 2. 입력으로 각도 조절
    current_angle = 90
    while True:
        command = input("명령 입력 (w: 증가, s: 감소, q: 종료): ").lower()
        if command == 'w':
            current_angle = min(current_angle + 5, 180)
            set_throttle(current_angle)
        elif command == 's':
            current_angle = max(current_angle - 5, 0)
            set_throttle(current_angle)
        elif command == 'q':
            break
        else:
            print("잘못된 입력. w, s, q 중 선택하세요.")

    # 마무리: 중립 복귀
    set_throttle(90)
    print("프로그램 종료. 중립으로 설정.")

except KeyboardInterrupt:
    pass
finally:
    set_throttle(90)  # 안전 중립 복귀
    print("프로그램 강제 종료. 중립으로 설정.")