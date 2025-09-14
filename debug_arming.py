#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESC ARM 신호 디버깅 전용 스크립트
PWM 1번 채널에 대한 다양한 ARM 시나리오를 테스트합니다.
"""

import time
import logging
import sys
from typing import List, Tuple

# GPIO 라이브러리 import 시도
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("✓ RPi.GPIO 사용 가능")
except ImportError:
    GPIO_AVAILABLE = False
    print("✗ RPi.GPIO 사용 불가")

try:
    import rpigpio
    RPI_GPIO_AVAILABLE = True
    print("✓ rpigpio 사용 가능")
except ImportError:
    RPI_GPIO_AVAILABLE = False
    print("✗ rpigpio 사용 불가")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ARMDebugger:
    """ESC ARM 디버깅 클래스"""
    
    def __init__(self, channel: int = 1):
        self.channel = channel
        self.pwm = None
        self.rpi_gpio = None
        self.hardware_type = None
        
    def setup_hardware(self, hardware_type: str = "auto") -> bool:
        """하드웨어 설정"""
        try:
            if hardware_type == "auto":
                if RPI_GPIO_AVAILABLE:
                    hardware_type = "rpigpio"
                elif GPIO_AVAILABLE:
                    hardware_type = "RPi.GPIO"
                else:
                    hardware_type = "simulation"
            
            if hardware_type == "rpigpio" and RPI_GPIO_AVAILABLE:
                self.rpi_gpio = rpigpio.RPiGPIO()
                self.hardware_type = "rpigpio"
                logger.info(f"rpigpio 초기화 완료 - 채널 {self.channel}")
                return True
                
            elif hardware_type == "RPi.GPIO" and GPIO_AVAILABLE:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.channel, GPIO.OUT)
                self.pwm = GPIO.PWM(self.channel, 50)  # 50Hz
                self.hardware_type = "RPi.GPIO"
                logger.info(f"RPi.GPIO 초기화 완료 - 채널 {self.channel}")
                return True
                
            else:
                self.hardware_type = "simulation"
                logger.info("시뮬레이션 모드")
                return True
                
        except Exception as e:
            logger.error(f"하드웨어 설정 실패: {e}")
            return False
    
    def send_pulse(self, pulse_width: int, duration: float = 1.0) -> bool:
        """펄스 신호 전송"""
        try:
            logger.info(f"펄스 전송: {pulse_width}us, {duration}초간")
            
            if self.hardware_type == "rpigpio":
                self.rpi_gpio.set_servo_pulsewidth(self.channel, pulse_width)
                time.sleep(duration)
                
            elif self.hardware_type == "RPi.GPIO":
                if not self.pwm._running:
                    self.pwm.start(0)
                duty_cycle = (pulse_width / 20000) * 100
                self.pwm.ChangeDutyCycle(duty_cycle)
                time.sleep(duration)
                
            else:  # simulation
                logger.info(f"시뮬레이션: {pulse_width}us 펄스 전송")
                time.sleep(duration)
            
            return True
            
        except Exception as e:
            logger.error(f"펄스 전송 실패: {e}")
            return False
    
    def test_basic_pwm(self) -> bool:
        """기본 PWM 테스트"""
        logger.info("=== 기본 PWM 테스트 ===")
        
        test_cases = [
            (1000, "최소 펄스"),
            (1500, "중립 펄스"),
            (2000, "최대 펄스"),
        ]
        
        for pulse_width, description in test_cases:
            logger.info(f"테스트: {description} ({pulse_width}us)")
            if not self.send_pulse(pulse_width, 2.0):
                return False
        
        return True
    
    def test_arm_sequence_1(self) -> bool:
        """ARM 시퀀스 1: 표준 방법"""
        logger.info("=== ARM 시퀀스 1: 표준 방법 ===")
        
        # 1. 최소 펄스로 ARM 시도
        logger.info("1단계: 최소 펄스 (1000us)로 ARM 시도")
        self.send_pulse(1000, 3.0)
        
        # 2. 중립으로 전환
        logger.info("2단계: 중립 펄스 (1500us)로 전환")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_arm_sequence_2(self) -> bool:
        """ARM 시퀀스 2: 긴 최소 펄스"""
        logger.info("=== ARM 시퀀스 2: 긴 최소 펄스 ===")
        
        # 1. 매우 긴 최소 펄스
        logger.info("1단계: 긴 최소 펄스 (1000us, 5초)")
        self.send_pulse(1000, 5.0)
        
        # 2. 중립으로 전환
        logger.info("2단계: 중립 펄스 (1500us)로 전환")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_arm_sequence_3(self) -> bool:
        """ARM 시퀀스 3: 펄스 폭 변화"""
        logger.info("=== ARM 시퀀스 3: 펄스 폭 변화 ===")
        
        # 1. 최소에서 중립으로 점진적 변화
        logger.info("1단계: 최소 펄스 (1000us)")
        self.send_pulse(1000, 2.0)
        
        logger.info("2단계: 중간 펄스 (1250us)")
        self.send_pulse(1250, 1.0)
        
        logger.info("3단계: 중립 펄스 (1500us)")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_arm_sequence_4(self) -> bool:
        """ARM 시퀀스 4: 반복 시도"""
        logger.info("=== ARM 시퀀스 4: 반복 시도 ===")
        
        for attempt in range(3):
            logger.info(f"시도 {attempt + 1}/3")
            
            # 최소 펄스
            self.send_pulse(1000, 2.0)
            
            # 중립 펄스
            self.send_pulse(1500, 1.0)
            
            # 잠시 대기
            time.sleep(1.0)
        
        return True
    
    def test_arm_sequence_5(self) -> bool:
        """ARM 시퀀스 5: 다양한 펄스 폭"""
        logger.info("=== ARM 시퀀스 5: 다양한 펄스 폭 ===")
        
        # 다양한 ARM 펄스 폭 테스트
        arm_pulses = [900, 950, 1000, 1050, 1100]
        
        for pulse in arm_pulses:
            logger.info(f"ARM 펄스 테스트: {pulse}us")
            self.send_pulse(pulse, 3.0)
            self.send_pulse(1500, 1.0)
            time.sleep(0.5)
        
        return True
    
    def test_continuous_signal(self) -> bool:
        """연속 신호 테스트"""
        logger.info("=== 연속 신호 테스트 ===")
        
        logger.info("최소 펄스 (1000us)를 10초간 연속 전송...")
        start_time = time.time()
        
        while time.time() - start_time < 10:
            self.send_pulse(1000, 0.1)
        
        logger.info("중립 펄스 (1500us)로 전환")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_frequency_variations(self) -> bool:
        """주파수 변화 테스트 (RPi.GPIO만)"""
        if self.hardware_type != "RPi.GPIO":
            logger.info("주파수 테스트는 RPi.GPIO에서만 가능")
            return True
        
        logger.info("=== 주파수 변화 테스트 ===")
        
        frequencies = [50, 100, 200, 300]
        
        for freq in frequencies:
            logger.info(f"주파수 {freq}Hz로 테스트")
            
            # PWM 재시작
            if self.pwm._running:
                self.pwm.stop()
            
            self.pwm = GPIO.PWM(self.channel, freq)
            self.pwm.start(0)
            
            # 최소 펄스 전송
            duty_cycle = (1000 / (1000000 / freq)) * 100
            self.pwm.ChangeDutyCycle(duty_cycle)
            time.sleep(2.0)
            
            # 중립 펄스 전송
            duty_cycle = (1500 / (1000000 / freq)) * 100
            self.pwm.ChangeDutyCycle(duty_cycle)
            time.sleep(1.0)
        
        return True
    
    def cleanup(self):
        """리소스 정리"""
        try:
            if self.pwm and self.pwm._running:
                self.pwm.stop()
            if GPIO_AVAILABLE:
                GPIO.cleanup()
            logger.info("리소스 정리 완료")
        except Exception as e:
            logger.error(f"정리 중 오류: {e}")

def main():
    """메인 함수"""
    print("ESC ARM 디버깅 스크립트")
    print("=" * 50)
    
    # 하드웨어 선택
    print("\n사용할 하드웨어를 선택하세요:")
    print("1. 자동 선택")
    print("2. rpigpio")
    print("3. RPi.GPIO")
    print("4. 시뮬레이션")
    
    choice = input("선택 (1-4): ").strip()
    
    hardware_map = {
        "1": "auto",
        "2": "rpigpio",
        "3": "RPi.GPIO",
        "4": "simulation"
    }
    
    hardware_type = hardware_map.get(choice, "auto")
    
    # 디버거 생성
    debugger = ARMDebugger(channel=1)
    
    if not debugger.setup_hardware(hardware_type):
        print("하드웨어 설정 실패")
        return
    
    print(f"\n사용 중인 하드웨어: {debugger.hardware_type}")
    print(f"PWM 채널: {debugger.channel}")
    
    try:
        # 테스트 시퀀스 실행
        test_sequences = [
            ("기본 PWM 테스트", debugger.test_basic_pwm),
            ("ARM 시퀀스 1", debugger.test_arm_sequence_1),
            ("ARM 시퀀스 2", debugger.test_arm_sequence_2),
            ("ARM 시퀀스 3", debugger.test_arm_sequence_3),
            ("ARM 시퀀스 4", debugger.test_arm_sequence_4),
            ("ARM 시퀀스 5", debugger.test_arm_sequence_5),
            ("연속 신호 테스트", debugger.test_continuous_signal),
            ("주파수 변화 테스트", debugger.test_frequency_variations),
        ]
        
        for name, test_func in test_sequences:
            print(f"\n{'='*20} {name} {'='*20}")
            input("Enter를 눌러 테스트 시작...")
            
            try:
                if test_func():
                    print(f"✓ {name} 완료")
                else:
                    print(f"✗ {name} 실패")
            except KeyboardInterrupt:
                print(f"\n{name} 중단됨")
                break
            except Exception as e:
                print(f"✗ {name} 오류: {e}")
        
        print("\n모든 테스트 완료")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")
    finally:
        debugger.cleanup()

if __name__ == "__main__":
    main()
