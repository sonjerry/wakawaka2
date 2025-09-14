import time
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정

# ESC 채널 번호 (예: 1번)
esc_channel = 1

# 펄스 폭을 angle로 매핑 (90° = 1500μs, 180° = 2000μs, 0° = 1000μs)
def set_throttle(angle):
    kit.servo[esc_channel].angle = angle  # 0-180도 범위
    pulse_width = int(1500 + (angle - 90) * 3.333)  # 90°=1500μs, 180°=2000μs, 0°=1000μs
    print(f"Throttle set to {angle}° (approx. {pulse_width}μs)")

# 동작 시퀀스
try:
    # 시작: 중립 (90°, 1500μs)
    set_throttle(90)
    print("중립 설정 (90°, 1500μs). 5초 대기.")
    time.sleep(5)

    # 사용자로부터 각도 입력 받기
    angle_input = int(input("유지할 각도를 입력하세요 (0-180): "))
    if 0 <= angle_input <= 180:
        set_throttle(angle_input)
        print(f"{angle_input}°로 설정. 5초 동안 유지.")
        time.sleep(5)
    else:
        print("유효한 각도(0-180)만 입력하세요. 중립으로 유지.")
    
    # 마무리: 중립 복귀
    set_throttle(90)
    print("중립으로 복귀 (90°, 1500μs).")

except KeyboardInterrupt:
    set_throttle(90)  # 안전 중립
    print("중단됨. 중립으로 설정.")
except ValueError:
    set_throttle(90)  # 잘못된 입력 시 중립
    print("숫자를 입력하세요. 중립으로 설정.")