#!/usr/bin/env python3
"""
ESC 아밍 문제 진단 및 테스트 스크립트
"""
import asyncio
import time
import config
import hardware

def print_esc_status():
    """ESC 현재 상태를 출력"""
    status = hardware.get_esc_status()
    print("\n=== ESC 상태 정보 ===")
    for key, value in status.items():
        print(f"{key}: {value}")
    print("=" * 30)

def test_duty_calculation():
    """duty cycle 계산 테스트"""
    print("\n=== Duty Cycle 계산 테스트 ===")
    test_values = [1000, 1500, 1800, 2000]
    for us in test_values:
        duty = hardware._us_to_duty(us)
        print(f"{us}us -> duty_cycle: {duty}")

async def test_esc_arming_sequence():
    """ESC 아밍 시퀀스 테스트"""
    print("\n=== ESC 아밍 시퀀스 테스트 ===")
    
    # 하드웨어 초기화
    hardware.init()
    print_esc_status()
    
    # 아밍 시퀀스 실행
    print("\nESC 아밍 시작...")
    await hardware.set_engine_enabled_async(True)
    print_esc_status()
    
    # 3초 대기 후 상태 확인
    print("\n3초 대기 후 상태 확인...")
    await asyncio.sleep(3)
    print_esc_status()
    
    # 디스아밍
    print("\nESC 디스아밍...")
    await hardware.set_engine_enabled_async(False)
    print_esc_status()

def test_individual_pulses():
    """개별 펄스 테스트"""
    print("\n=== 개별 펄스 테스트 ===")
    
    hardware.init()
    
    test_pulses = [
        (1000, "최소 펄스"),
        (1500, "중간 펄스"),
        (1800, "중립 펄스"),
        (2000, "최대 펄스")
    ]
    
    for us, description in test_pulses:
        print(f"\n{description} ({us}us) 전송...")
        hardware.test_esc_pulse(us)
        time.sleep(2)  # 2초 대기
    
    # 안전 상태로 복귀
    print("\n안전 상태로 복귀...")
    hardware.set_safe_state()
    print_esc_status()

async def main():
    """메인 테스트 함수"""
    print("ESC 아밍 문제 진단 스크립트 시작")
    print("=" * 50)
    
    # 1. Duty cycle 계산 테스트
    test_duty_calculation()
    
    # 2. 개별 펄스 테스트
    test_individual_pulses()
    
    # 3. 전체 아밍 시퀀스 테스트
    await test_esc_arming_sequence()
    
    # 정리
    hardware.shutdown()
    print("\n테스트 완료!")

if __name__ == "__main__":
    asyncio.run(main())
