#!/usr/bin/env python3
"""
ESC 캘리브레이션 도구
사용법: python calibrate_esc.py
"""

import asyncio
import time
import config
import hardware

async def calibrate_esc():
    """ESC 캘리브레이션을 수행합니다."""
    print("=== ESC 캘리브레이션 도구 ===")
    print("주의: 바퀴를 지면에서 들어올리거나 차량을 안전하게 고정하세요!")
    print()
    
    # 하드웨어 상태 확인
    print("하드웨어 라이브러리 상태 확인 중...")
    print(f"hardware_present: {hardware.hardware_present}")
    
    if not hardware.hardware_present:
        print("❌ 하드웨어 라이브러리가 설치되지 않았습니다!")
        print("다음 명령어로 설치하세요:")
        print("pip install adafruit-circuitpython-pca9685")
        print("pip install adafruit-circuitpython-busio")
        return
    
    # 하드웨어 초기화
    try:
        print("하드웨어 초기화 시도 중...")
        hardware.init()
        print("✅ 하드웨어 초기화 완료")
        print(f"PCA9685 객체: {hardware.pca}")
    except Exception as e:
        print(f"❌ 하드웨어 초기화 실패: {e}")
        print("I2C 연결을 확인하세요 (SCL, SDA 핀)")
        return
    
    print("\n1. ESC를 완전히 끄기...")
    hardware.set_safe_state()
    await asyncio.sleep(1.0)
    
    print("2. 최대값(2000us)으로 설정...")
    max_duty = hardware._us_to_duty(2000)
    hardware.pca.channels[config.CH_ESC].duty_cycle = max_duty
    print("   ESC에 전원을 켜세요! (3초 대기)")
    await asyncio.sleep(3.0)
    
    print("3. 최소값(1000us)으로 설정...")
    min_duty = hardware._us_to_duty(1000)
    hardware.pca.channels[config.CH_ESC].duty_cycle = min_duty
    print("   ESC가 비프음으로 캘리브레이션 완료를 알릴 것입니다 (3초 대기)")
    await asyncio.sleep(3.0)
    
    print("4. 중립값(1500us)으로 설정...")
    neutral_duty = hardware._us_to_duty(1500)
    hardware.pca.channels[config.CH_ESC].duty_cycle = neutral_duty
    print("   모터가 정지 상태인지 확인하세요")
    await asyncio.sleep(2.0)
    
    print("\n=== 캘리브레이션 완료 ===")
    print("모터가 정지하지 않는다면 config.py의 ESC_TRIM_US 값을 조정하세요:")
    print("- 모터가 천천히 전진한다면: ESC_TRIM_US = -50 ~ -200")
    print("- 모터가 천천히 후진한다면: ESC_TRIM_US = 50 ~ 200")
    
    # 정리
    hardware.set_safe_state()
    hardware.shutdown()

if __name__ == "__main__":
    asyncio.run(calibrate_esc())
