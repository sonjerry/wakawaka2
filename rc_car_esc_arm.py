import time
import board
import busio
from adafruit_pca9685 import PCA9685

# --- I2C 및 PCA9685 초기화 ---
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# --- RC카 ESC용 PWM 값 정의 ---
# 이 값들은 ESC 제조사에 따라 미세 조정이 필요할 수 있습니다.
THROTTLE_REVERSE_MAX = 3280  # 약 1.0ms 펄스 (최대 후진)
THROTTLE_NEUTRAL = 4912      # 약 1.5ms 펄스 (중립/정지)
THROTTLE_FORWARD_MAX = 6560  # 약 2.0ms 펄스 (최대 전진)

# 사용할 PCA9685 채널 번호 (0 ~ 15)
ESC_CHANNEL = 1
esc = pca.channels[ESC_CHANNEL]

def arm_car_esc():
    """RC카 ESC를 중립 신호로 아밍하는 함수"""
    print("RC카 ESC 아밍을 시작합니다.")
    print(f"채널 {ESC_CHANNEL}에 중립(Neutral) 신호({THROTTLE_NEUTRAL})를 보냅니다.")
    
    # 아밍을 위해 반드시 중립 신호를 먼저 보내야 합니다.
    esc.duty_cycle = THROTTLE_NEUTRAL
    time.sleep(2) # ESC가 신호를 인식할 시간을 줍니다.
    
    print("아밍 완료! 이제 주행이 가능합니다.")

try:
    # 1. ESC 아밍 실행
    arm_car_esc()

    # 2. 주행 테스트
    print("\n--- 주행 테스트 시작 ---")
    
    # 약한 전진 (3초)
    print("약하게 전진합니다...")
    esc.duty_cycle = int(THROTTLE_NEUTRAL * 1.1) # 중립보다 10% 높은 값
    time.sleep(3)
    
    # 정지 (2초)
    print("정지합니다...")
    esc.duty_cycle = THROTTLE_NEUTRAL
    time.sleep(2)
    
    # 약한 후진 (3초)
    # 참고: 일부 ESC는 후진을 위해 중립->브레이크->중립->후진 같은 복잡한 과정을 거칩니다.
    #      여기서는 단순 후진 신호를 보냅니다.
    print("약하게 후진합니다...")
    esc.duty_cycle = int(THROTTLE_NEUTRAL * 0.9) # 중립보다 10% 낮은 값
    time.sleep(3)

except KeyboardInterrupt:
    print("\n프로그램을 중지합니다.")

finally:
    # 안전하게 중립 상태로 모터 정지
    print("안전을 위해 모터를 정지(중립) 상태로 되돌립니다.")
    esc.duty_cycle = THROTTLE_NEUTRAL
    time.sleep(1)
    pca.deinit()
    print("리소스가 정리되었습니다.")