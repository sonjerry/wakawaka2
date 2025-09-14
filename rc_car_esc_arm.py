import time
import board
import busio
from adafruit_pca9685 import PCA9685

# --- 설정 ---
# I2C 버스 초기화
i2c = busio.I2C(board.SCL, board.SDA)

# PCA9685 객체 생성
pca = PCA9685(i2c)

# ESC가 사용하는 PWM 주파수 설정 (보통 50Hz)
pca.frequency = 50

# 1ms, 2ms 펄스에 해당하는 16비트 duty_cycle 값 계산
# 이 값은 ESC에 따라 미세 조정이 필요할 수 있습니다.
THROTTLE_MIN = 3280  # 약 1ms 펄스 (최소 스로틀)
THROTTLE_MAX = 6560  # 약 2ms 펄스 (최대 스로틀)

# 사용할 PCA9685 채널 번호 (0번 ~ 15번)
ESC_CHANNEL = 1

# --- 메인 코드 ---
# 특정 채널을 변수로 지정하여 사용
esc = pca.channels[ESC_CHANNEL]

def arm_esc():
    """ESC를 아밍하는 함수"""
    print("ESC 아밍을 시작합니다. 모터에서 '삐' 소리가 나는지 확인하세요.")
    print(f"채널 {ESC_CHANNEL}에 최소 스로틀({THROTTLE_MIN}) 신호를 3초간 보냅니다.")
    
    # 아밍을 위해 최소 스로틀 신호를 보냄
    esc.duty_cycle = THROTTLE_MIN
    time.sleep(3)
    
    print("아밍 완료! 이제 모터를 제어할 수 있습니다.")

try:
    # ESC 아밍 함수 실행
    arm_esc()

    # 아밍 후 모터 테스트 (스로틀을 살짝 올려보기)
    print("\n모터 회전 테스트를 시작합니다 (3초간).")
    test_throttle = int(THROTTLE_MIN * 1.15) # 최소 스로틀의 115% 값
    print(f"테스트 스로틀: {test_throttle}")
    esc.duty_cycle = test_throttle
    time.sleep(3)
    
    print("\n테스트 종료. 스로틀을 최소로 되돌립니다.")
    esc.duty_cycle = THROTTLE_MIN
    time.sleep(1)

except KeyboardInterrupt:
    print("\n프로그램을 중지합니다.")

finally:
    # 프로그램 종료 시 안전하게 모터 정지
    print("안전을 위해 모터를 정지합니다.")
    esc.duty_cycle = THROTTLE_MIN
    time.sleep(1)
    pca.deinit() # PCA9685 리소스 해제
    print("리소스가 정리되었습니다.")