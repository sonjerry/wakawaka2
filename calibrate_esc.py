#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESC 캘리브레이션 도구
펄스 임계치를 1부터 3000까지 천천히 올려서 ESC의 반응을 확인합니다.
"""

import time
import config
import hardware

def calibrate_esc():
    """ESC 캘리브레이션 실행"""
    print("=== ESC 캘리브레이션 시작 ===")
    print("ESC가 연결되어 있는지 확인하세요.")
    print("ESC의 비프음과 모터 반응을 주의깊게 관찰하세요.")
    print("캘리브레이션 중에는 ESC를 만지지 마세요!")
    print()
    
    # 하드웨어 초기화
    hardware.init()
    
    # 사용자 확인
    input("준비가 되면 Enter를 누르세요...")
    print()
    
    try:
        # ESC 아밍 먼저 수행
        print("1. ESC 아밍 중...")
        import asyncio
        asyncio.run(hardware.set_engine_enabled_async(True))
        print("ESC 아밍 완료!")
        print()
        
        # 펄스 범위 설정 (캘리브레이션된 범위)
        min_pulse = 1600  # ESC 최소값
        max_pulse = 1800  # ESC 최대값 (8% 속도)
        step = 1
        delay = 0.1  # 각 단계마다 0.1초 대기
        
        print(f"2. 펄스 캘리브레이션 시작 ({min_pulse}us ~ {max_pulse}us)")
        print(f"   단계: {step}us, 지연: {delay}초")
        print("   ESC의 반응을 주의깊게 관찰하세요!")
        print()
        
        # 펄스를 천천히 올리기
        for pulse_us in range(min_pulse, max_pulse + 1, step):
            # ESC에 펄스 전송
            duty = hardware._us_to_duty(pulse_us)
            if hardware.hardware_present and hardware.pca is not None:
                hardware.pca.channels[config.CH_ESC].duty_cycle = duty
            
            # 진행 상황 표시 (100us마다)
            if pulse_us % 100 == 0:
                print(f"펄스: {pulse_us:4d}us (듀티: {duty:5d})", end="\r")
            
            # 잠시 대기
            time.sleep(delay)
        
        print(f"\n펄스: {max_pulse:4d}us (듀티: {hardware._us_to_duty(max_pulse):5d})")
        print()
        
        # 최대 펄스에서 잠시 대기
        print("3. 최대 펄스에서 3초 대기...")
        time.sleep(3)
        
        # 펄스를 천천히 내리기
        print("4. 펄스를 천천히 내리는 중...")
        for pulse_us in range(max_pulse, min_pulse - 1, -step):
            duty = hardware._us_to_duty(pulse_us)
            if hardware.hardware_present and hardware.pca is not None:
                hardware.pca.channels[config.CH_ESC].duty_cycle = duty
            
            # 진행 상황 표시 (100us마다)
            if pulse_us % 100 == 0:
                print(f"펄스: {pulse_us:4d}us (듀티: {duty:5d})", end="\r")
            
            time.sleep(delay)
        
        print(f"\n펄스: {min_pulse:4d}us (듀티: {hardware._us_to_duty(min_pulse):5d})")
        print()
        
        # 중립 펄스로 설정
        print("5. 중립 펄스로 설정...")
        neutral_duty = hardware._us_to_duty(config.ESC_NEUTRAL_US)
        if hardware.hardware_present and hardware.pca is not None:
            hardware.pca.channels[config.CH_ESC].duty_cycle = neutral_duty
        print(f"중립 펄스: {config.ESC_NEUTRAL_US}us (듀티: {neutral_duty})")
        
        print()
        print("=== ESC 캘리브레이션 완료 ===")
        print("관찰한 내용을 바탕으로 config.py의 ESC 설정값을 조정하세요:")
        print(f"  ESC_MIN_US = {config.ESC_MIN_US}  # 최소 펄스 (후진/브레이크)")
        print(f"  ESC_NEUTRAL_US = {config.ESC_NEUTRAL_US}  # 중립 펄스 (정지)")
        print(f"  ESC_MAX_US = {config.ESC_MAX_US}  # 최대 펄스 (전진)")
        
    except KeyboardInterrupt:
        print("\n\n캘리브레이션이 중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
    finally:
        # 안전 상태로 복원
        print("\n안전 상태로 복원 중...")
        hardware.set_safe_state()
        hardware.shutdown()
        print("완료!")

def quick_test():
    """빠른 테스트 - 주요 펄스값들만 테스트"""
    print("=== ESC 빠른 테스트 ===")
    print("주요 펄스값들을 테스트합니다.")
    print("1600us: 최소값 (후진/브레이크)")
    print("1700us: 중립값 (정지)")
    print("1800us: 최대값 (8% 속도)")
    print()
    
    hardware.init()
    
    try:
        # ESC 아밍
        print("ESC 아밍 중...")
        import asyncio
        asyncio.run(hardware.set_engine_enabled_async(True))
        print("아밍 완료!")
        print()
        
        # 테스트할 펄스값들 (캘리브레이션된 범위)
        test_pulses = [1600, 1650, 1700, 1750, 1800]
        
        for pulse_us in test_pulses:
            print(f"펄스 {pulse_us}us 테스트 중... (3초)")
            duty = hardware._us_to_duty(pulse_us)
            if hardware.hardware_present and hardware.pca is not None:
                hardware.pca.channels[config.CH_ESC].duty_cycle = duty
            time.sleep(3)
        
        print("테스트 완료!")
        
    except KeyboardInterrupt:
        print("\n테스트가 중단되었습니다.")
    finally:
        hardware.set_safe_state()
        hardware.shutdown()

if __name__ == "__main__":
    print("ESC 캘리브레이션 도구")
    print("1. 전체 캘리브레이션 (1us ~ 3000us)")
    print("2. 빠른 테스트 (주요 펄스값들만)")
    print()
    
    choice = input("선택하세요 (1 또는 2): ").strip()
    
    if choice == "1":
        calibrate_esc()
    elif choice == "2":
        quick_test()
    else:
        print("잘못된 선택입니다.")
