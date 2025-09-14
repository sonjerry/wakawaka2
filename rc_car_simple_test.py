#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RC카용 ESC 간단 테스트 스크립트
RC카용 ESC의 핵심 ARM 시퀀스를 빠르게 테스트합니다.
"""

import time
import sys

def test_rc_car_standard_arm():
    """RC카 표준 ARM 시퀀스"""
    try:
        import RPi.GPIO as GPIO
        print("RC카 표준 ARM 시퀀스 시작...")
        
        channel = 1
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(channel, GPIO.OUT)
        
        pwm = GPIO.PWM(channel, 50)  # 50Hz
        pwm.start(0)
        
        # 1. 중립 신호 (스로틀 최저 위치)
        print("1단계: 중립 신호 (1500us) - 스로틀 최저 위치")
        pwm.ChangeDutyCycle(7.5)  # 1500us = 7.5%
        time.sleep(2)
        
        # 2. 최대 신호 (스로틀 최고 위치)
        print("2단계: 최대 신호 (2000us) - 스로틀 최고 위치")
        pwm.ChangeDutyCycle(10.0)  # 2000us = 10%
        time.sleep(2)
        
        # 3. 다시 중립으로 (스로틀 최저 위치)
        print("3단계: 중립 신호 (1500us) - 스로틀 최저 위치")
        pwm.ChangeDutyCycle(7.5)  # 1500us = 7.5%
        time.sleep(2)
        
        pwm.stop()
        GPIO.cleanup()
        print("RC카 표준 ARM 시퀀스 완료")
        return True
        
    except ImportError:
        print("RPi.GPIO 모듈을 찾을 수 없습니다")
        return False
    except Exception as e:
        print(f"RC카 표준 ARM 실패: {e}")
        return False

def test_rc_car_calibration_arm():
    """RC카 캘리브레이션 ARM 시퀀스"""
    try:
        import RPi.GPIO as GPIO
        print("RC카 캘리브레이션 ARM 시퀀스 시작...")
        
        channel = 1
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(channel, GPIO.OUT)
        
        pwm = GPIO.PWM(channel, 50)  # 50Hz
        pwm.start(0)
        
        # 1. 중립 신호로 시작
        print("1단계: 중립 신호 (1500us) 시작")
        pwm.ChangeDutyCycle(7.5)  # 1500us = 7.5%
        time.sleep(1)
        
        # 2. 최대 신호로 캘리브레이션 시작
        print("2단계: 최대 신호 (2000us) - 캘리브레이션 시작")
        pwm.ChangeDutyCycle(10.0)  # 2000us = 10%
        time.sleep(3)
        
        # 3. 최소 신호로 캘리브레이션 완료
        print("3단계: 최소 신호 (1000us) - 캘리브레이션 완료")
        pwm.ChangeDutyCycle(5.0)  # 1000us = 5%
        time.sleep(3)
        
        # 4. 중립으로 복귀
        print("4단계: 중립 신호 (1500us) - ARM 완료")
        pwm.ChangeDutyCycle(7.5)  # 1500us = 7.5%
        time.sleep(2)
        
        pwm.stop()
        GPIO.cleanup()
        print("RC카 캘리브레이션 ARM 시퀀스 완료")
        return True
        
    except ImportError:
        print("RPi.GPIO 모듈을 찾을 수 없습니다")
        return False
    except Exception as e:
        print(f"RC카 캘리브레이션 ARM 실패: {e}")
        return False

def test_rc_car_neutral_only():
    """RC카 중립 신호만 전송"""
    try:
        import RPi.GPIO as GPIO
        print("RC카 중립 신호만 전송...")
        
        channel = 1
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(channel, GPIO.OUT)
        
        pwm = GPIO.PWM(channel, 50)  # 50Hz
        pwm.start(0)
        
        # 중립 신호를 10초간 연속 전송
        print("중립 신호 (1500us)를 10초간 연속 전송...")
        pwm.ChangeDutyCycle(7.5)  # 1500us = 7.5%
        time.sleep(10)
        
        pwm.stop()
        GPIO.cleanup()
        print("RC카 중립 신호 전송 완료")
        return True
        
    except ImportError:
        print("RPi.GPIO 모듈을 찾을 수 없습니다")
        return False
    except Exception as e:
        print(f"RC카 중립 신호 실패: {e}")
        return False

def test_rc_car_brake_sequence():
    """RC카 브레이크 시퀀스"""
    try:
        import RPi.GPIO as GPIO
        print("RC카 브레이크 시퀀스 시작...")
        
        channel = 1
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(channel, GPIO.OUT)
        
        pwm = GPIO.PWM(channel, 50)  # 50Hz
        pwm.start(0)
        
        # 1. 중립 신호
        print("1단계: 중립 신호 (1500us)")
        pwm.ChangeDutyCycle(7.5)  # 1500us = 7.5%
        time.sleep(1)
        
        # 2. 브레이크 신호 (역방향)
        print("2단계: 브레이크 신호 (1000us)")
        pwm.ChangeDutyCycle(5.0)  # 1000us = 5%
        time.sleep(2)
        
        # 3. 다시 중립
        print("3단계: 중립 신호 (1500us)")
        pwm.ChangeDutyCycle(7.5)  # 1500us = 7.5%
        time.sleep(2)
        
        pwm.stop()
        GPIO.cleanup()
        print("RC카 브레이크 시퀀스 완료")
        return True
        
    except ImportError:
        print("RPi.GPIO 모듈을 찾을 수 없습니다")
        return False
    except Exception as e:
        print(f"RC카 브레이크 시퀀스 실패: {e}")
        return False

def main():
    print("RC카용 ESC 간단 테스트")
    print("=" * 30)
    
    tests = [
        ("RC카 표준 ARM", test_rc_car_standard_arm),
        ("RC카 캘리브레이션 ARM", test_rc_car_calibration_arm),
        ("RC카 중립 신호만", test_rc_car_neutral_only),
        ("RC카 브레이크 시퀀스", test_rc_car_brake_sequence),
    ]
    
    for name, test_func in tests:
        print(f"\n{name} 테스트:")
        print("-" * 20)
        
        try:
            if test_func():
                print(f"✓ {name} 성공")
            else:
                print(f"✗ {name} 실패")
        except KeyboardInterrupt:
            print(f"\n{name} 중단됨")
            break
        except Exception as e:
            print(f"✗ {name} 오류: {e}")
        
        input("Enter를 눌러 다음 테스트...")

if __name__ == "__main__":
    main()
