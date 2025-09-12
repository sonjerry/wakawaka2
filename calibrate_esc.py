# esc_calibrate_pca9685.py
import time
from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio

I2C_ADDR = 0x40
CHANNEL = 1          # "1번 채널"
FREQ_HZ = 50

MIN_US = 1000
MID_US = 1500
MAX_US = 2000
BIDIRECTIONAL = True

# PCA9685는 12-bit(0~4095). 1사이클 = 20ms(50Hz)이므로 1us=4096/20000≈0.2048 카운트
def us_to_counts(us):
    return int(us * 4096 / 20000)

def write_us(pca, ch, us):
    ch.duty_cycle = us_to_counts(us)

if __name__ == "__main__":
    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c, address=I2C_ADDR)
    pca.frequency = FREQ_HZ
    ch = pca.channels[CHANNEL]

    try:
        print("\n=== ESC 캘리브레이션 (PCA9685 CH1) ===")
        input("1) ESC 전원을 분리한 상태에서 Enter ")
        write_us(pca, ch, MAX_US)
        print(f"[출력] MAX {MAX_US}us")
        input("2) ESC 배터리 전원을 연결하고 비프가 나면 Enter ")

        write_us(pca, ch, MIN_US)
        print(f"[출력] MIN {MIN_US}us (저장 단계)")
        time.sleep(2.0)

        if BIDIRECTIONAL:
            write_us(pca, ch, MID_US)
            print(f"[출력] MID {MID_US}us (중립 세팅)")
            time.sleep(1.5)

        print("캘리브레이션 완료. 아밍은 전원 직후 MIN(일방향)/MID(양방향) 2~3초 유지.")

    finally:
        # 안전 정지: 펄스 유지가 필요한 ESC가 많으므로 중립으로 둔 채 종료
        write_us(pca, ch, MID_US if BIDIRECTIONAL else MIN_US)
        time.sleep(0.5)
        # 필요시 완전 정지하고 싶으면 duty_cycle=0로 끊어도 됨(일부 ESC는 싫어할 수 있음)
        # ch.duty_cycle = 0
        pca.deinit()
