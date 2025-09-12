#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESC 모터 제어 디버깅 코드
라즈베리파이에서 PWM을 통해 ESC 모듈을 제어하여 모터의 다양한 속도와 방향을 테스트합니다.

ESC 제어 범위:
- 1000μs: 정지/최저 속도 (뒤로 최대)
- 1500μs: 중립 (정지)
- 2000μs: 최고 속도 (앞으로 최대)
"""

import RPi.GPIO as GPIO
import time
import sys
import signal

class ESCController:
    def __init__(self, pwm_pin=18, frequency=50):
        """
        ESC 컨트롤러 초기화
        
        Args:
            pwm_pin (int): PWM 출력 핀 번호 (기본값: 18)
            frequency (int): PWM 주파수 (기본값: 50Hz)
        """
        self.pwm_pin = pwm_pin
        self.frequency = frequency
        self.pwm = None
        self.current_duty = 0
        
        # ESC 제어 범위 (마이크로초)
        self.MIN_PULSE = 1000  # 최소 펄스 폭 (정지/최저 속도)
        self.MAX_PULSE = 2000  # 최대 펄스 폭 (최고 속도)
        self.NEUTRAL_PULSE = 1500  # 중립 펄스 폭
        
        # 안전을 위한 제한값
        self.MIN_SAFE_DUTY = 5.0   # 5% (1000μs)
        self.MAX_SAFE_DUTY = 10.0  # 10% (2000μs)
        self.NEUTRAL_DUTY = 7.5    # 7.5% (1500μs)
        
        self.setup_gpio()
        
    def setup_gpio(self):
        """GPIO 설정 및 PWM 초기화"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pwm_pin, GPIO.OUT)
            
            # PWM 객체 생성 (50Hz, 7.5% 듀티 사이클로 시작)
            self.pwm = GPIO.PWM(self.pwm_pin, self.frequency)
            self.pwm.start(self.NEUTRAL_DUTY)
            self.current_duty = self.NEUTRAL_DUTY
            
            print(f"✓ GPIO 설정 완료 (핀: {self.pwm_pin}, 주파수: {self.frequency}Hz)")
            print(f"✓ PWM 초기화 완료 (듀티 사이클: {self.NEUTRAL_DUTY}%)")
            
        except Exception as e:
            print(f"❌ GPIO 설정 오류: {e}")
            sys.exit(1)
    
    def pulse_width_to_duty(self, pulse_width_us):
        """
        펄스 폭(μs)을 듀티 사이클(%)로 변환
        
        Args:
            pulse_width_us (int): 펄스 폭 (마이크로초)
            
        Returns:
            float: 듀티 사이클 (%)
        """
        # 50Hz = 20ms 주기
        # 듀티 사이클 = (펄스 폭 / 20000) * 100
        duty = (pulse_width_us / 20000.0) * 100.0
        return max(self.MIN_SAFE_DUTY, min(self.MAX_SAFE_DUTY, duty))
    
    def set_motor_speed(self, pulse_width_us):
        """
        모터 속도 설정
        
        Args:
            pulse_width_us (int): 펄스 폭 (마이크로초)
        """
        if not self.pwm:
            print("❌ PWM이 초기화되지 않았습니다.")
            return
            
        duty = self.pulse_width_to_duty(pulse_width_us)
        
        try:
            self.pwm.ChangeDutyCycle(duty)
            self.current_duty = duty
            
            # 방향 및 속도 정보 출력
            if pulse_width_us < self.NEUTRAL_PULSE:
                direction = "뒤로"
                speed = "저속" if pulse_width_us < 1200 else "중속"
            elif pulse_width_us > self.NEUTRAL_PULSE:
                direction = "앞으로"
                speed = "중속" if pulse_width_us < 1800 else "고속"
            else:
                direction = "중립"
                speed = "정지"
            
            print(f"🔧 모터 설정: {direction} {speed} (펄스: {pulse_width_us}μs, 듀티: {duty:.1f}%)")
            
        except Exception as e:
            print(f"❌ 모터 속도 설정 오류: {e}")
    
    def arm_esc(self):
        """ESC 아밍 (초기화)"""
        print("🔄 ESC 아밍 중...")
        
        # 최대 펄스로 시작 (아밍)
        self.set_motor_speed(self.MAX_PULSE)
        time.sleep(2)
        
        # 최소 펄스로 이동 (아밍 완료)
        self.set_motor_speed(self.MIN_PULSE)
        time.sleep(2)
        
        # 중립으로 이동
        self.set_motor_speed(self.NEUTRAL_PULSE)
        time.sleep(1)
        
        print("✓ ESC 아밍 완료")
    
    def test_speed_range(self):
        """전체 속도 범위 테스트"""
        print("\n🚀 전체 속도 범위 테스트 시작")
        print("=" * 50)
        
        # 테스트할 펄스 폭 값들
        test_values = [
            (1000, "정지/최저 속도 (뒤로 최대)"),
            (1100, "매우 저속 (뒤로)"),
            (1200, "저속 (뒤로)"),
            (1300, "중저속 (뒤로)"),
            (1400, "중저속 (뒤로)"),
            (1500, "중립 (정지)"),
            (1600, "중저속 (앞으로)"),
            (1700, "중저속 (앞으로)"),
            (1800, "저속 (앞으로)"),
            (1900, "중속 (앞으로)"),
            (2000, "최고 속도 (앞으로 최대)")
        ]
        
        for pulse_width, description in test_values:
            print(f"\n📊 테스트: {description}")
            self.set_motor_speed(pulse_width)
            time.sleep(3)  # 3초간 유지
        
        # 테스트 완료 후 중립으로
        print("\n🏁 테스트 완료 - 중립으로 복귀")
        self.set_motor_speed(self.NEUTRAL_PULSE)
    
    def interactive_control(self):
        """대화형 모터 제어"""
        print("\n🎮 대화형 모터 제어 모드")
        print("=" * 30)
        print("명령어:")
        print("  w: 앞으로 최대 속도 (2000μs)")
        print("  s: 뒤로 최대 속도 (1000μs)")
        print("  a: 앞으로 저속 (1600μs)")
        print("  d: 뒤로 저속 (1400μs)")
        print("  space: 중립 (1500μs)")
        print("  q: 종료")
        print("  t: 전체 범위 테스트")
        print("  h: 도움말")
        print("=" * 30)
        
        while True:
            try:
                command = input("\n명령어 입력: ").lower().strip()
                
                if command == 'q':
                    print("프로그램을 종료합니다...")
                    break
                elif command == 'w':
                    self.set_motor_speed(2000)
                elif command == 's':
                    self.set_motor_speed(1000)
                elif command == 'a':
                    self.set_motor_speed(1600)
                elif command == 'd':
                    self.set_motor_speed(1400)
                elif command == ' ' or command == 'space':
                    self.set_motor_speed(1500)
                elif command == 't':
                    self.test_speed_range()
                elif command == 'h':
                    print("도움말을 다시 표시합니다.")
                    continue
                else:
                    print("❌ 잘못된 명령어입니다. 'h'를 입력하여 도움말을 확인하세요.")
                    
            except KeyboardInterrupt:
                print("\n프로그램을 종료합니다...")
                break
            except Exception as e:
                print(f"❌ 오류 발생: {e}")
    
    def cleanup(self):
        """리소스 정리"""
        print("\n🧹 리소스 정리 중...")
        
        if self.pwm:
            self.pwm.stop()
            print("✓ PWM 정지")
        
        GPIO.cleanup()
        print("✓ GPIO 정리 완료")
    
    def __del__(self):
        """소멸자"""
        self.cleanup()

def signal_handler(sig, frame):
    """시그널 핸들러 (Ctrl+C 처리)"""
    print("\n\n⚠️  프로그램이 중단되었습니다.")
    print("모터를 안전하게 중립으로 설정합니다...")
    sys.exit(0)

def main():
    """메인 함수"""
    print("🤖 ESC 모터 제어 디버깅 프로그램")
    print("=" * 40)
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # ESC 컨트롤러 생성
        esc = ESCController(pwm_pin=18)  # GPIO 18번 핀 사용
        
        # ESC 아밍
        esc.arm_esc()
        
        # 대화형 제어 시작
        esc.interactive_control()
        
    except KeyboardInterrupt:
        print("\n프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        # 리소스 정리
        if 'esc' in locals():
            esc.cleanup()

if __name__ == "__main__":
    main()
