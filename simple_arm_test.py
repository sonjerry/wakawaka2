#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간단한 ESC ARM 테스트 스크립트
PWM 1번 채널에 직접 ARM 신호를 전송합니다.
"""

import time
import sys

def test_rpigpio():
    """rpigpio로 ARM 테스트"""
    try:
        import rpigpio
        print("rpigpio로 ARM 테스트 시작...")
        
        rpi = rpigpio.RPiGPIO()
        channel = 1
        
        print(f"채널 {channel}에 최소 펄스 (1000us) 전송...")
        rpi.set_servo_pulsewidth(channel, 1000)
        time.sleep(3)
        
        print(f"채널 {channel}에 중립 펄스 (1500us) 전송...")
        rpi.set_servo_pulsewidth(channel, 1500)
        time.sleep(2)
        
        print("ARM 테스트 완료")
        rpi.stop()
        return True
        
    except ImportError:
        print("rpigpio 모듈을 찾을 수 없습니다")
        return False
    except Exception as e:
        print(f"rpigpio 테스트 실패: {e}")
        return False

def test_rpi_gpio():
    """RPi.GPIO로 ARM 테스트"""
    try:
        import RPi.GPIO as GPIO
        print("RPi.GPIO로 ARM 테스트 시작...")
        
        channel = 1
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(channel, GPIO.OUT)
        
        pwm = GPIO.PWM(channel, 50)  # 50Hz
        pwm.start(0)
        
        # 최소 펄스 (1000us = 5% 듀티 사이클)
        print(f"채널 {channel}에 최소 펄스 (1000us) 전송...")
        pwm.ChangeDutyCycle(5.0)
        time.sleep(3)
        
        # 중립 펄스 (1500us = 7.5% 듀티 사이클)
        print(f"채널 {channel}에 중립 펄스 (1500us) 전송...")
        pwm.ChangeDutyCycle(7.5)
        time.sleep(2)
        
        pwm.stop()
        GPIO.cleanup()
        print("ARM 테스트 완료")
        return True
        
    except ImportError:
        print("RPi.GPIO 모듈을 찾을 수 없습니다")
        return False
    except Exception as e:
        print(f"RPi.GPIO 테스트 실패: {e}")
        return False

def test_manual_pwm():
    """수동 PWM 테스트 (RPi.GPIO)"""
    try:
        import RPi.GPIO as GPIO
        print("수동 PWM 테스트 시작...")
        
        channel = 1
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(channel, GPIO.OUT)
        
        # 50Hz = 20ms 주기
        period = 0.02  # 20ms
        min_pulse = 0.001  # 1ms
        neutral_pulse = 0.0015  # 1.5ms
        
        print(f"채널 {channel}에 최소 펄스 (1ms) 전송...")
        for _ in range(150):  # 3초간 (50Hz * 3초)
            GPIO.output(channel, GPIO.HIGH)
            time.sleep(min_pulse)
            GPIO.output(channel, GPIO.LOW)
            time.sleep(period - min_pulse)
        
        print(f"채널 {channel}에 중립 펄스 (1.5ms) 전송...")
        for _ in range(100):  # 2초간
            GPIO.output(channel, GPIO.HIGH)
            time.sleep(neutral_pulse)
            GPIO.output(channel, GPIO.LOW)
            time.sleep(period - neutral_pulse)
        
        GPIO.cleanup()
        print("수동 PWM 테스트 완료")
        return True
        
    except ImportError:
        print("RPi.GPIO 모듈을 찾을 수 없습니다")
        return False
    except Exception as e:
        print(f"수동 PWM 테스트 실패: {e}")
        return False

def main():
    print("ESC ARM 간단 테스트")
    print("=" * 30)
    
    tests = [
        ("rpigpio", test_rpigpio),
        ("RPi.GPIO", test_rpi_gpio),
        ("수동 PWM", test_manual_pwm),
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
