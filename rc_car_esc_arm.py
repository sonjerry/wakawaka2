#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RC카용 ESC ARM 디버깅 스크립트
RC카용 ESC의 특별한 ARM 시퀀스를 테스트합니다.
"""

import time
import logging
import sys

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

class RCCarESCArm:
    """RC카용 ESC ARM 클래스"""
    
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
    
    def test_rc_car_arm_sequence_1(self) -> bool:
        """RC카 ESC ARM 시퀀스 1: 표준 RC카 방법"""
        logger.info("=== RC카 ESC ARM 시퀀스 1: 표준 방법 ===")
        
        # 1. 중립 신호로 시작 (스로틀 최저 위치)
        logger.info("1단계: 중립 신호 (1500us) - 스로틀 최저 위치")
        self.send_pulse(1500, 2.0)
        
        # 2. 최대 신호 (스로틀 최고 위치)
        logger.info("2단계: 최대 신호 (2000us) - 스로틀 최고 위치")
        self.send_pulse(2000, 2.0)
        
        # 3. 다시 중립으로 (스로틀 최저 위치)
        logger.info("3단계: 중립 신호 (1500us) - 스로틀 최저 위치")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_rc_car_arm_sequence_2(self) -> bool:
        """RC카 ESC ARM 시퀀스 2: 캘리브레이션 방법"""
        logger.info("=== RC카 ESC ARM 시퀀스 2: 캘리브레이션 방법 ===")
        
        # 1. 중립 신호로 시작
        logger.info("1단계: 중립 신호 (1500us) 시작")
        self.send_pulse(1500, 1.0)
        
        # 2. 최대 신호로 캘리브레이션 시작
        logger.info("2단계: 최대 신호 (2000us) - 캘리브레이션 시작")
        self.send_pulse(2000, 3.0)
        
        # 3. 최소 신호로 캘리브레이션 완료
        logger.info("3단계: 최소 신호 (1000us) - 캘리브레이션 완료")
        self.send_pulse(1000, 3.0)
        
        # 4. 중립으로 복귀
        logger.info("4단계: 중립 신호 (1500us) - ARM 완료")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_rc_car_arm_sequence_3(self) -> bool:
        """RC카 ESC ARM 시퀀스 3: 점진적 변화"""
        logger.info("=== RC카 ESC ARM 시퀀스 3: 점진적 변화 ===")
        
        # 1. 중립에서 시작
        logger.info("1단계: 중립 신호 (1500us)")
        self.send_pulse(1500, 1.0)
        
        # 2. 점진적으로 최대까지
        logger.info("2단계: 점진적 증가")
        for pulse in range(1500, 2001, 100):
            logger.info(f"  펄스: {pulse}us")
            self.send_pulse(pulse, 0.5)
        
        # 3. 점진적으로 최소까지
        logger.info("3단계: 점진적 감소")
        for pulse in range(2000, 999, -100):
            logger.info(f"  펄스: {pulse}us")
            self.send_pulse(pulse, 0.5)
        
        # 4. 중립으로 복귀
        logger.info("4단계: 중립 신호 (1500us)")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_rc_car_arm_sequence_4(self) -> bool:
        """RC카 ESC ARM 시퀀스 4: 반복 시도"""
        logger.info("=== RC카 ESC ARM 시퀀스 4: 반복 시도 ===")
        
        for attempt in range(3):
            logger.info(f"시도 {attempt + 1}/3")
            
            # 중립 → 최대 → 최소 → 중립
            self.send_pulse(1500, 1.0)
            self.send_pulse(2000, 2.0)
            self.send_pulse(1000, 2.0)
            self.send_pulse(1500, 1.0)
            
            time.sleep(1.0)
        
        return True
    
    def test_rc_car_arm_sequence_5(self) -> bool:
        """RC카 ESC ARM 시퀀스 5: 특별한 펄스 폭"""
        logger.info("=== RC카 ESC ARM 시퀀스 5: 특별한 펄스 폭 ===")
        
        # RC카용 특별한 펄스 폭들
        special_pulses = [
            (1100, "낮은 중립"),
            (1200, "중간 낮음"),
            (1300, "중간"),
            (1400, "중간 높음"),
            (1500, "중립"),
            (1600, "중간 높음"),
            (1700, "중간"),
            (1800, "중간 낮음"),
            (1900, "높은 중립"),
        ]
        
        for pulse, description in special_pulses:
            logger.info(f"테스트: {description} ({pulse}us)")
            self.send_pulse(pulse, 2.0)
            self.send_pulse(1500, 1.0)
            time.sleep(0.5)
        
        return True
    
    def test_rc_car_arm_sequence_6(self) -> bool:
        """RC카 ESC ARM 시퀀스 6: 연속 중립 신호"""
        logger.info("=== RC카 ESC ARM 시퀀스 6: 연속 중립 신호 ===")
        
        logger.info("중립 신호 (1500us)를 10초간 연속 전송...")
        start_time = time.time()
        
        while time.time() - start_time < 10:
            self.send_pulse(1500, 0.1)
        
        logger.info("연속 중립 신호 전송 완료")
        return True
    
    def test_rc_car_arm_sequence_7(self) -> bool:
        """RC카 ESC ARM 시퀀스 7: 브레이크 신호"""
        logger.info("=== RC카 ESC ARM 시퀀스 7: 브레이크 신호 ===")
        
        # 1. 중립 신호
        logger.info("1단계: 중립 신호 (1500us)")
        self.send_pulse(1500, 1.0)
        
        # 2. 브레이크 신호 (역방향)
        logger.info("2단계: 브레이크 신호 (1000us)")
        self.send_pulse(1000, 2.0)
        
        # 3. 다시 중립
        logger.info("3단계: 중립 신호 (1500us)")
        self.send_pulse(1500, 2.0)
        
        return True
    
    def test_rc_car_arm_sequence_8(self) -> bool:
        """RC카 ESC ARM 시퀀스 8: 전원 순서"""
        logger.info("=== RC카 ESC ARM 시퀀스 8: 전원 순서 ===")
        
        # 1. 신호 없이 시작
        logger.info("1단계: 신호 없음 (0us)")
        if self.hardware_type == "rpigpio":
            self.rpi_gpio.set_servo_pulsewidth(self.channel, 0)
        elif self.hardware_type == "RPi.GPIO":
            if self.pwm._running:
                self.pwm.stop()
        time.sleep(2.0)
        
        # 2. 중립 신호 시작
        logger.info("2단계: 중립 신호 (1500us) 시작")
        if self.hardware_type == "RPi.GPIO" and not self.pwm._running:
            self.pwm.start(0)
        self.send_pulse(1500, 3.0)
        
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
    print("RC카용 ESC ARM 디버깅 스크립트")
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
    debugger = RCCarESCArm(channel=1)
    
    if not debugger.setup_hardware(hardware_type):
        print("하드웨어 설정 실패")
        return
    
    print(f"\n사용 중인 하드웨어: {debugger.hardware_type}")
    print(f"PWM 채널: {debugger.channel}")
    
    try:
        # RC카용 테스트 시퀀스 실행
        test_sequences = [
            ("RC카 ARM 시퀀스 1", debugger.test_rc_car_arm_sequence_1),
            ("RC카 ARM 시퀀스 2", debugger.test_rc_car_arm_sequence_2),
            ("RC카 ARM 시퀀스 3", debugger.test_rc_car_arm_sequence_3),
            ("RC카 ARM 시퀀스 4", debugger.test_rc_car_arm_sequence_4),
            ("RC카 ARM 시퀀스 5", debugger.test_rc_car_arm_sequence_5),
            ("RC카 ARM 시퀀스 6", debugger.test_rc_car_arm_sequence_6),
            ("RC카 ARM 시퀀스 7", debugger.test_rc_car_arm_sequence_7),
            ("RC카 ARM 시퀀스 8", debugger.test_rc_car_arm_sequence_8),
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
