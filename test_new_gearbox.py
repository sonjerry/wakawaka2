#!/usr/bin/env python3
"""
새로운 8단 변속기 시스템 테스트 스크립트
"""
import sys
import time
import config
from simulation import VehicleModel, ShiftState

def test_gearbox_system():
    """변속기 시스템을 테스트합니다."""
    print("=== 새로운 8단 변속기 시스템 테스트 ===")
    
    # 차량 모델 생성
    vehicle = VehicleModel()
    vehicle.engine_running = True
    vehicle.gear = "D"
    vehicle.virtual_gear = 1
    
    print(f"초기 상태: 기어={vehicle.virtual_gear}, vRPM={vehicle.vrpm:.0f}, 속도={vehicle.speed_est:.2f}m/s")
    print(f"입력 처리: axis={vehicle.axis}, throttle={vehicle.throttle_intent:.2f}, brake={vehicle.brake_intent:.2f}")
    
    # 테스트 시나리오: 가속하여 변속 테스트
    dt = 0.01  # 100Hz
    
    print("\n=== 가속 테스트 (스로틀 50%) ===")
    for i in range(500):  # 5초간
        inputs = {"axis": 25.0, "steer_dir": 0}  # 스로틀 50%
        vehicle.update(dt, inputs)
        
        if i % 50 == 0:  # 0.5초마다 출력
            print(f"t={i*dt:.1f}s: 기어={vehicle.virtual_gear}, vRPM={vehicle.vrpm:.0f}, "
                  f"속도={vehicle.speed_est:.2f}m/s, wheel_speed={vehicle.wheel_speed:.3f}, "
                  f"토크={vehicle.torque_cmd:.1f}%, 변속상태={vehicle.shift_state.value}")
    
    print("\n=== 브레이크 테스트 ===")
    for i in range(200):  # 2초간
        inputs = {"axis": -30.0, "steer_dir": 0}  # 브레이크 60%
        vehicle.update(dt, inputs)
        
        if i % 20 == 0:  # 0.2초마다 출력
            print(f"t={i*dt:.1f}s: 기어={vehicle.virtual_gear}, vRPM={vehicle.vrpm:.0f}, "
                  f"속도={vehicle.speed_est:.2f}m/s, wheel_speed={vehicle.wheel_speed:.3f}, "
                  f"토크={vehicle.torque_cmd:.1f}%, 변속상태={vehicle.shift_state.value}")
    
    print("\n=== 크리프 테스트 (페달 해제) ===")
    for i in range(100):  # 1초간
        inputs = {"axis": 0.0, "steer_dir": 0}  # 페달 해제
        vehicle.update(dt, inputs)
        
        if i % 20 == 0:  # 0.2초마다 출력
            print(f"t={i*dt:.1f}s: 기어={vehicle.virtual_gear}, vRPM={vehicle.vrpm:.0f}, "
                  f"속도={vehicle.speed_est:.2f}m/s, wheel_speed={vehicle.wheel_speed:.3f}, "
                  f"토크={vehicle.torque_cmd:.1f}%, 변속상태={vehicle.shift_state.value}")

def test_gear_ratios():
    """기어비를 테스트합니다."""
    print("\n=== 기어비 테스트 ===")
    vehicle = VehicleModel()
    vehicle.engine_running = True
    vehicle.gear = "D"
    
    for gear in range(1, 9):
        vehicle.virtual_gear = gear
        vehicle.speed_est = 5.0  # 5 m/s 고정
        vehicle._update_vrpm()
        
        print(f"기어 {gear}: 기어비={vehicle.gear_ratios[gear-1]:.2f}, "
              f"vRPM={vehicle.vrpm:.0f}, 토크스케일={vehicle.gear_torque_scale[gear-1]:.2f}")

def test_shift_timing():
    """변속 타이밍을 테스트합니다."""
    print("\n=== 변속 타이밍 테스트 ===")
    vehicle = VehicleModel()
    vehicle.engine_running = True
    vehicle.gear = "D"
    vehicle.virtual_gear = 1
    
    # 고속으로 가속하여 업시프트 유도
    inputs = {"axis": 50.0, "steer_dir": 0}  # 스로틀 100%
    
    shift_count = 0
    for i in range(1000):  # 10초간
        vehicle.update(0.01, inputs)
        
        if vehicle.shift_state != ShiftState.READY and shift_count < 3:
            print(f"변속 #{shift_count + 1}: {vehicle.shift_state.value} "
                  f"(기어 {vehicle.virtual_gear} → {vehicle.shift_target_gear})")
            shift_count += 1

if __name__ == "__main__":
    try:
        test_gearbox_system()
        test_gear_ratios()
        test_shift_timing()
        print("\n✅ 모든 테스트 완료!")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
