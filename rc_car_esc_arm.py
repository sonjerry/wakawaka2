import time
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정

# ESC 채널 번호 (예: 0번)
esc_channel = 1

# 펄스 폭을 angle로 매핑 (90° = 1700μs, 180° = 2000μs, 0° = 1000μs)
def set_throttle(angle):
    kit.servo[esc_channel].angle = angle  # 0-180도 범위
    pulse_width = int(1500 + (angle - 90) * 3.333)  # 90°=1700μs, 180°=2000μs, 0°=1000μs
    print(f"Throttle set to {angle}° (approx. {pulse_width}μs)")

# 동작 시퀀스
try:
    # 시작: 중립 (90°, 1700μs)
    set_throttle(90)
    print("중립 설정 (90°, 1500μs). 5초 대기.")
    time.sleep(5)

    set_throttle(95)
    time.sleep(1)
    print("95")
    set_throttle(100)
    time.sleep(1)
    print("100")
    set_throttle(105)
    time.sleep(1)
    print("105")
    set_throttle(110)
    time.sleep(1)
    print("110")
    set_throttle(115)
    time.sleep(1)
    print("115")

    set_throttle(90)
    time.sleep(1)
    print("90")
    set_throttle(85)
    time.sleep(1)
    print("100")
    set_throttle(80)
    time.sleep(1)
    print("105")
    set_throttle(70)
    time.sleep(1)
    print("110")
    set_throttle(50)
    time.sleep(1)
    print("115")

except KeyboardInterrupt:
    set_throttle(90)  # 안전 중립
    print("중단됨. 중립으로 설정.")