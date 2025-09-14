import time
from adafruit_servokit import ServoKit

# PCA9685 모터 드라이버의 채널 수에 맞게 설정 (보통 16)
kit = ServoKit(channels=16)

# ESC가 연결된 채널 번호 (예: 0번 채널)
ESC_CHANNEL = 0

# 1. Arming: 중립 위치(90도)로 설정
print("ESC Arming 시작: 중립 위치(90도)로 설정합니다.")
kit.servo[ESC_CHANNEL].angle = 90
time.sleep(2) # ESC가 신호를 인식할 시간을 줌
print("Arming 완료. 이제 제어 가능합니다.")

# 이제부터 전진, 후진, 브레이크 제어가 가능합니다.