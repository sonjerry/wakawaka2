import time
from adafruit_servokit import ServoKit

# ServoKit 초기화 (PCA9685, 16채널)
kit = ServoKit(channels=16)

# ESC 채널 번호 (예: 0번)
esc_channel = 1

# 펄스 폭 설정 함수 (μs 단위, ESC에 맞춤)
def set_throttle(pulse_width):
    # ServoKit에서 pulse width 직접 설정 (angle 대신 사용)
    kit.servo[esc_channel].set_pulse_width(pulse_width)  # 1000-2000μs 범위
    print(f"Throttle set to {pulse_width}μs")

# 캘리브레이션 시퀀스
try:
    # 1. 전원 OFF 상태에서 중립 신호 미리 설정 (배터리 연결 전)
    set_throttle(1500)  # 중립
    print("중립 신호 설정. 이제 배터리 연결하세요 (전원 ON).")
    input("Enter 누르면 계속...")  # 배터리 연결 대기

    # 2. 배터리 연결 후 (ESC 비프음 1-2회 나야 함, LiPo면 셀 수만큼 + 긴 비프)
    time.sleep(2)  # ESC가 부팅할 시간

    # 3. 최대 신호 보내기 (ESC가 2회 비프음 내며 학습)
    set_throttle(2000)
    print("최대 신호 보냄. 2회 비프 확인.")
    time.sleep(2)

    # 4. 최소 신호 보내기 (ESC가 1회 비프음 내며 학습, 브레이크)
    set_throttle(1000)
    print("최소 신호 보냄. 1회 비프 확인.")
    time.sleep(2)

    # 5. 다시 중립으로 (ESC가 준비 비프 후 LED 켜짐)
    set_throttle(1500)
    print("중립으로 복귀. 캘리브레이션 완료! 이제 throttle 조절 테스트.")

    # 테스트: 서서히 앞으로 (비프 없고 모터 돌기 시작)
    for pw in range(1500, 2000, 50):
        set_throttle(pw)
        time.sleep(0.5)
    set_throttle(1500)  # 중립 복귀

except KeyboardInterrupt:
    set_throttle(1500)  # 안전 중립
    print("중단됨. 중립으로 설정.")