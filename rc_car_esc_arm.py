import time
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정

# ESC 채널 번호 (예: 1번)
esc_channel = 1

# 펄스 폭을 angle로 매핑 (90° = 1599μs 기준)
def set_throttle(angle):
    if angle == 90:
        pulse_width = 1599  # 90° 고정
    elif angle < 90:
        # 0°~90°: 1000μs ~ 1599μs (599μs 증가)
        pulse_width = 1000 + (angle / 90) * 599
    else:
        # 90°~180°: 1599μs ~ 2000μs (401μs 증가)
        pulse_width = 1599 + ((angle - 90) / 90) * 401
    # ServoKit는 angle로 제어 (실제 펄스 폭은 라이브러리 매핑에 의존)
    kit.servo[esc_channel].angle = angle
    print(f"Throttle set to {angle}° (calculated {pulse_width:.1f}μs)")

# 동작 시퀀스 (이전처럼 입력받아 5초 유지)
try:
    # 시작: 중립 (90°, 1599μs)
    set_throttle(0)
    print("중립 설정 ")
    time.sleep(1)
    set_throttle(180)
    time.sleep(1)

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
    print("중립으로 복귀 (90°, 1599μs).")

except KeyboardInterrupt:
    set_throttle(90)  # 안전 중립
    print("중단됨. 중립으로 설정.")
except ValueError:
    set_throttle(90)  # 잘못된 입력 시 중립
    print("숫자를 입력하세요. 중립으로 설정.")