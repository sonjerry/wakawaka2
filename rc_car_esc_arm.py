import time
from board import SCL, SDA
import busio
from adafruit_servokit import ServoKit

# I2C 버스 및 ServoKit 초기화
# PCA9685의 기본 주소는 0x40 입니다. 주소가 다를 경우 address=0x?? 로 수정하세요.
# channels=16은 PCA9685가 16개의 채널을 가지고 있음을 의미합니다.
try:
    i2c = busio.I2C(SCL, SDA)
    kit = ServoKit(channels=16, i2c=i2c)
    print("PCA9685가 성공적으로 초기화되었습니다.")
except Exception as e:
    print(f"오류: PCA9685를 찾을 수 없거나 초기화에 실패했습니다. I2C 연결을 확인하세요.")
    print(e)
    exit()

# ESC가 연결된 채널 설정
ESC_CHANNEL = 1  # 1번 채널에 연결됨

# ESC 펄스 폭 범위 설정 (대부분의 ESC는 1000-2000µs 범위에서 작동)
# 필요에 따라 이 값을 미세 조정할 수 있습니다.
# set_pulse_width_range(min_pulse, max_pulse)
kit.servo[ESC_CHANNEL].set_pulse_width_range(1000, 2000)
print("ESC 펄스 폭 범위를 1000µs에서 2000µs로 설정했습니다.")

def arm_esc():
    """ESC를 arming(활성화)합니다. 중립 신호를 보내 안전하게 시작할 수 있도록 준비시킵니다."""
    print("\nESC Arming을 시작합니다...")
    # 중립 위치(정지)로 설정합니다. 90도가 보통 중립입니다.
    kit.servo[ESC_CHANNEL].angle = 90
    print("중립 신호(90도)를 보내는 중... ESC에서 신호음이 날 때까지 3초간 기다립니다.")
    time.sleep(3)
    print("ESC Arming이 완료되었습니다.")

def run_motor():
    """모터를 정방향과 역방향으로 최고속, 최저속으로 구동합니다."""
    # --- 정방향 테스트 ---
    print("\n--- 정방향 테스트 ---")
    
    # 정방향 최저속 (중립에서 약간 벗어난 값)
    print("정방향 최저속으로 2초간 구동합니다.")
    kit.servo[ESC_CHANNEL].angle = 100
    time.sleep(2)

    # 정방향 최고속
    print("정방향 최고속으로 3초간 구동합니다.")
    kit.servo[ESC_CHANNEL].angle = 180
    time.sleep(3)
    
    # 정지
    print("모터를 정지합니다.")
    kit.servo[ESC_CHANNEL].angle = 90
    time.sleep(2) # 방향 전환 전 잠시 대기

    # --- 역방향 테스트 ---
    print("\n--- 역방향 테스트 ---")
    
    # 역방향 최저속 (중립에서 약간 벗어난 값)
    print("역방향 최저속으로 2초간 구동합니다.")
    kit.servo[ESC_CHANNEL].angle = 80
    time.sleep(2)

    # 역방향 최고속
    print("역방향 최고속으로 3초간 구동합니다.")
    kit.servo[ESC_CHANNEL].angle = 0
    time.sleep(3)

    # 정지
    print("모터를 정지합니다.")
    kit.servo[ESC_CHANNEL].angle = 90
    time.sleep(1)

def main():
    """메인 실행 함수"""
    try:
        # 1. ESC Arming
        arm_esc()

        # 2. 모터 구동 테스트
        run_motor()

        print("\n테스트가 완료되었습니다.")

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다. 모터를 정지합니다.")
        kit.servo[ESC_CHANNEL].angle = 90 # 안전을 위해 모터 정지
    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
        kit.servo[ESC_CHANNEL].angle = 90 # 안전을 위해 모터 정지

if __name__ == '__main__':
    main()