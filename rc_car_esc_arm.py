import time
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)
kit.frequency = 50  # 50Hz로 명시적 설정

# ESC 채널 번호 (예: 0번)
esc_channel = 1

# 펄스 폭을 angle로 매핑 (0° = 1000μs, 90° = 1500μs, 180° = 2000μs)
def set_throttle(angle):
    kit.servo[esc_channel].angle = angle  # 0-180도 범위
    pulse_width = int(angle * 5.555 + 1000)  # 대략적인 μs 계산
    print(f"Throttle set to {angle}° (approx. {pulse_width}μs)")

# 캘리브레이션 시퀀스
try:
    # 1. 전원 OFF 상태에서 중립 신호 미리 설정
    set_throttle(90)  # 중립 (1500μs)
    print("중립 신호 설정. 이제 배터리 연결하세요 (전원 ON).")
    input("Enter 누르면 계속...")  # 배터리 연결 대기

    # 2. 배터리 연결 후 초기화 대기
    time.sleep(5)  # ESC 부팅 시간 충분히 확보

    # 3. 최대 신호 보내기 (ESC가 2회 비프음 내며 학습)
    set_throttle(180)  # 최대 (2000μs)
    print("최대 신호 보냄. 2회 비프 확인 후 5초 대기.")
    time.sleep(5)

    # 4. 최소 신호 보내기 (ESC가 1회 비프음 내며 학습, 브레이크)
    set_throttle(0)  # 최소 (1000μs)
    print("최소 신호 보냄. 1회 비프 확인 후 5초 대기.")
    time.sleep(5)

    # 5. 다시 중립으로 (ESC가 준비 비프 후 LED 켜짐)
    set_throttle(90)  # 중립 복귀
    print("중립으로 복귀. 캘리브레이션 완료! 5초 대기 후 테스트.")

    time.sleep(5)

    # 테스트: 서서히 앞으로
    for angle in range(90, 181, 5):
        set_throttle(angle)
        time.sleep(0.5)
    set_throttle(90)  # 중립 복귀

except KeyboardInterrupt:
    set_throttle(90)  # 안전 중립
    print("중단됨. 중립으로 설정.")