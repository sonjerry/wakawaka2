import time
from adafruit_servokit import ServoKit

# PCA9685 보드의 채널 수 설정
kit = ServoKit(channels=16)

# ESC가 연결된 채널 번호
ESC_CHANNEL = 1

# 대부분의 ESC는 1000µs(최소) ~ 2000µs(최대) 범위에서 작동합니다.
# adafruit_servokit의 기본값이 이와 다를 수 있으므로 명시적으로 설정해주는 것이 좋습니다.
# 이 값은 ESC 설명서에 따라 미세 조정이 필요할 수 있습니다.
min_pulse_width = 1800
max_pulse_width = 2200
kit.servo[ESC_CHANNEL].set_pulse_width_range(min_pulse_width, max_pulse_width)

def calibrate_esc():
    """ESC 스로틀 범위를 보정하는 함수"""
    print("ESC 보정을 시작합니다. RC카 배터리는 아직 연결하지 마세요.")
    print("3초 후에 최대 스로틀(180도) 신호를 보냅니다...")
    time.sleep(3)

    # 1. 최대 스로틀(180도) 신호 전송
    kit.servo[ESC_CHANNEL].angle = 180
    print("최대 스로틀 신호 전송 중. 이제 RC카의 배터리를 연결하세요.")
    print("ESC에서 '삑' 소리가 난 후, 다른 '삑-삑' 소리가 날 때까지 기다리세요.")
    
    # 사용자가 배터리를 연결하고 ESC 비프음을 들을 시간을 줍니다.
    # 보통 5~10초 정도 소요됩니다.
    input("비프음(삑-삑)을 들었다면 Enter 키를 누르세요...")

    # 2. 최소 스로틀(0도) 신호 전송
    print("최소 스로틀(0도) 신호를 보냅니다.")
    kit.servo[ESC_CHANNEL].angle = 0
    print("잠시 후 긴 '삐---' 소리와 함께 arming 비프음이 들립니다.")
    
    # ESC가 최소값을 저장하고 arming을 완료할 시간을 줍니다.
    time.sleep(5)
    
    # 3. 중립 위치(90도)로 이동
    print("보정이 완료되었습니다. 중립 위치(90도)로 이동합니다.")
    kit.servo[ESC_CHANNEL].angle = 90
    time.sleep(2)
    print("이제 ESC를 제어할 수 있습니다.")


# --- 메인 코드 실행 ---
calibrate_esc()

# 보정 후 테스트
print("테스트: 약하게 전진 (3초)")
kit.servo[ESC_CHANNEL].angle = 100
time.sleep(3)

print("테스트: 정지 (3초)")
kit.servo[ESC_CHANNEL].angle = 90
time.sleep(3)

print("테스트 종료")