import time
import keyboard  # 키보드 입력을 위해 pip install keyboard 필요 (RPi에서 sudo pip install keyboard)
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정

# ESC 채널 번호 (예: 1번)
esc_channel = 1

# 펄스 폭을 angle로 선형 매핑 (0° = 1000μs, 90° = 1599μs, 180° = 2198μs)
def set_throttle(angle):
    # 0°에서 180°까지 선형 매핑: 1000 + (angle / 180) * 1198 (2198 - 1000)
    pulse_width = int(1000 + (angle / 180) * 1198)  # 90° = 1599μs 근사
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
    print("Arming 완료. w/s 키로 각도 조절 (w: 증가, s: 감소). q로 종료.")

    # 2. 키보드 입력으로 각도 직접 조절
    current_angle = 90
    step = 5  # 각도 변화 스텝 (조정 가능)
    while True:
        if keyboard.is_pressed('w'):
            current_angle = min(current_angle + step, 180)
            set_throttle(current_angle)  # w키로 바로 조절
            time.sleep(0.2)  # 디바운스
        elif keyboard.is_pressed('s'):
            current_angle = max(current_angle - step, 0)
            set_throttle(current_angle)  # s키로 바로 조절
            time.sleep(0.2)  # 디바운스
        elif keyboard.is_pressed('q'):
            break
        time.sleep(0.05)  # 루프 딜레이

except KeyboardInterrupt:
    pass
finally:
    set_throttle(90)  # 안전 중립 복귀
    print("프로그램 종료. 중립으로 설정.")