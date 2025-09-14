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

    # 정방향: 90°에서 180°까지 천천히 상승
    for angle in range(90, 181, 5):
        set_throttle(angle)
        time.sleep(0.5)

    # 90°로 짧게 유지
    set_throttle(90)
    print("90° 유지. 2초 대기.")
    time.sleep(2)

    # 역방향: 90°에서 0°까지 천천히 하강
    for angle in range(90, -1, -5):
        set_throttle(angle)
        time.sleep(1)

    # 마무리: 중립 복귀
    set_throttle(90)
    print("중립으로 복귀 (90°, 1700μs).")

except KeyboardInterrupt:
    set_throttle(90)  # 안전 중립
    print("중단됨. 중립으로 설정.")