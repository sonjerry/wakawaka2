#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESC DC모터 제어 하드웨어 모듈
PWM 신호를 사용하여 1번 채널에 연결된 ESC로 DC모터를 제어합니다.
"""

import time
import threading
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("경고: RPi.GPIO 모듈을 찾을 수 없습니다. 시뮬레이션 모드로 실행됩니다.")

try:
    import rpigpio
    RPI_GPIO_AVAILABLE = True
except ImportError:
    RPI_GPIO_AVAILABLE = False
    print("경고: rpigpio 모듈을 찾을 수 없습니다. RPi.GPIO를 사용합니다.")


class MotorState(Enum):
    """모터 상태 열거형"""
    STOPPED = "stopped"
    RUNNING = "running"
    BRAKING = "braking"
    ERROR = "error"


@dataclass
class MotorConfig:
    """모터 설정 클래스"""
    channel: int = 1  # PWM 채널 (1번)
    frequency: int = 50  # PWM 주파수 (Hz) - ESC 표준
    min_pulse_width: int = 1000  # 최소 펄스 폭 (마이크로초)
    max_pulse_width: int = 2000  # 최대 펄스 폭 (마이크로초)
    neutral_pulse_width: int = 1500  # 중립 펄스 폭 (마이크로초)
    arm_pulse_width: int = 1000  # ARM 펄스 폭 (마이크로초)
    safety_timeout: float = 5.0  # 안전 타임아웃 (초)


class ESCController:
    """ESC DC모터 제어기 클래스"""
    
    def __init__(self, config: MotorConfig = None):
        """
        ESC 제어기 초기화
        
        Args:
            config: 모터 설정 (기본값 사용 가능)
        """
        self.config = config or MotorConfig()
        self.state = MotorState.STOPPED
        self.current_speed = 0.0  # -1.0 ~ 1.0 (음수는 역방향)
        self.is_armed = False
        self.last_command_time = 0.0
        self.safety_thread = None
        self.safety_running = False
        
        # PWM 객체
        self.pwm = None
        self.rpi_gpio = None
        
        # 로깅 설정
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 콜백 함수들
        self.on_state_change: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        self._initialize_hardware()
        self._start_safety_monitor()
    
    def _initialize_hardware(self):
        """하드웨어 초기화"""
        try:
            if RPI_GPIO_AVAILABLE:
                # rpigpio 사용 (더 정확한 PWM 제어)
                self.rpi_gpio = rpigpio.RPiGPIO()
                self.logger.info("rpigpio를 사용하여 PWM 초기화 완료")
            elif GPIO_AVAILABLE:
                # RPi.GPIO 사용
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.config.channel, GPIO.OUT)
                self.pwm = GPIO.PWM(self.config.channel, self.config.frequency)
                self.logger.info("RPi.GPIO를 사용하여 PWM 초기화 완료")
            else:
                # 시뮬레이션 모드
                self.logger.warning("하드웨어 모듈을 찾을 수 없습니다. 시뮬레이션 모드로 실행됩니다.")
                
        except Exception as e:
            self.logger.error(f"하드웨어 초기화 실패: {e}")
            self.state = MotorState.ERROR
            if self.on_error:
                self.on_error(f"하드웨어 초기화 실패: {e}")
    
    def _start_safety_monitor(self):
        """안전 모니터링 스레드 시작"""
        self.safety_running = True
        self.safety_thread = threading.Thread(target=self._safety_monitor, daemon=True)
        self.safety_thread.start()
        self.logger.info("안전 모니터링 스레드 시작")
    
    def _safety_monitor(self):
        """안전 모니터링 루프"""
        while self.safety_running:
            current_time = time.time()
            
            # 안전 타임아웃 체크
            if (current_time - self.last_command_time > self.config.safety_timeout and 
                self.state == MotorState.RUNNING):
                self.logger.warning("안전 타임아웃 발생 - 모터 정지")
                self.emergency_stop()
            
            time.sleep(0.1)  # 100ms 간격으로 체크
    
    def _set_pwm_pulse_width(self, pulse_width: int):
        """
        PWM 펄스 폭 설정
        
        Args:
            pulse_width: 펄스 폭 (마이크로초)
        """
        try:
            if self.rpi_gpio:
                # rpigpio 사용
                self.rpi_gpio.set_servo_pulsewidth(self.config.channel, pulse_width)
            elif self.pwm:
                # RPi.GPIO 사용
                duty_cycle = (pulse_width / 20000) * 100  # 20ms = 20000us
                self.pwm.ChangeDutyCycle(duty_cycle)
            else:
                # 시뮬레이션 모드
                self.logger.debug(f"시뮬레이션: PWM 펄스 폭 {pulse_width}us 설정")
                
        except Exception as e:
            self.logger.error(f"PWM 설정 실패: {e}")
            self.state = MotorState.ERROR
            if self.on_error:
                self.on_error(f"PWM 설정 실패: {e}")
    
    def arm(self) -> bool:
        """
        ESC ARM (모터 활성화)
        
        Returns:
            bool: ARM 성공 여부
        """
        try:
            if self.state == MotorState.ERROR:
                self.logger.error("오류 상태에서 ARM 시도")
                return False
            
            self.logger.info("ESC ARM 시작...")
            
            # ARM 시퀀스 실행
            self._set_pwm_pulse_width(self.config.arm_pulse_width)
            time.sleep(2.0)  # 2초 대기
            
            self.is_armed = True
            self.state = MotorState.STOPPED
            self.last_command_time = time.time()
            
            self.logger.info("ESC ARM 완료")
            if self.on_state_change:
                self.on_state_change(self.state)
            
            return True
            
        except Exception as e:
            self.logger.error(f"ESC ARM 실패: {e}")
            self.state = MotorState.ERROR
            if self.on_error:
                self.on_error(f"ESC ARM 실패: {e}")
            return False
    
    def set_speed(self, speed: float) -> bool:
        """
        모터 속도 설정
        
        Args:
            speed: 속도 (-1.0 ~ 1.0, 음수는 역방향)
            
        Returns:
            bool: 설정 성공 여부
        """
        try:
            if not self.is_armed:
                self.logger.warning("ESC가 ARM되지 않음")
                return False
            
            if self.state == MotorState.ERROR:
                self.logger.error("오류 상태에서 속도 설정 시도")
                return False
            
            # 속도 범위 제한
            speed = max(-1.0, min(1.0, speed))
            
            # 펄스 폭 계산
            if speed == 0:
                pulse_width = self.config.neutral_pulse_width
                self.state = MotorState.STOPPED
            else:
                # 선형 변환: -1.0~1.0 -> min_pulse_width~max_pulse_width
                range_width = self.config.max_pulse_width - self.config.min_pulse_width
                pulse_width = self.config.neutral_pulse_width + (speed * range_width / 2)
                pulse_width = int(pulse_width)
                self.state = MotorState.RUNNING
            
            # PWM 설정
            self._set_pwm_pulse_width(pulse_width)
            
            self.current_speed = speed
            self.last_command_time = time.time()
            
            self.logger.debug(f"모터 속도 설정: {speed:.2f} (펄스 폭: {pulse_width}us)")
            
            if self.on_state_change:
                self.on_state_change(self.state)
            
            return True
            
        except Exception as e:
            self.logger.error(f"속도 설정 실패: {e}")
            self.state = MotorState.ERROR
            if self.on_error:
                self.on_error(f"속도 설정 실패: {e}")
            return False
    
    def stop(self) -> bool:
        """
        모터 정지
        
        Returns:
            bool: 정지 성공 여부
        """
        return self.set_speed(0.0)
    
    def emergency_stop(self) -> bool:
        """
        비상 정지
        
        Returns:
            bool: 정지 성공 여부
        """
        try:
            self.logger.warning("비상 정지 실행")
            
            # 즉시 중립 신호 전송
            self._set_pwm_pulse_width(self.config.neutral_pulse_width)
            
            self.current_speed = 0.0
            self.state = MotorState.STOPPED
            self.last_command_time = time.time()
            
            if self.on_state_change:
                self.on_state_change(self.state)
            
            return True
            
        except Exception as e:
            self.logger.error(f"비상 정지 실패: {e}")
            self.state = MotorState.ERROR
            if self.on_error:
                self.on_error(f"비상 정지 실패: {e}")
            return False
    
    def get_status(self) -> dict:
        """
        현재 상태 정보 반환
        
        Returns:
            dict: 상태 정보
        """
        return {
            "state": self.state.value,
            "speed": self.current_speed,
            "is_armed": self.is_armed,
            "last_command_time": self.last_command_time,
            "config": {
                "channel": self.config.channel,
                "frequency": self.config.frequency,
                "min_pulse_width": self.config.min_pulse_width,
                "max_pulse_width": self.config.max_pulse_width,
                "neutral_pulse_width": self.config.neutral_pulse_width,
            }
        }
    
    def cleanup(self):
        """리소스 정리"""
        try:
            self.logger.info("ESC 제어기 정리 중...")
            
            # 안전 모니터링 스레드 종료
            self.safety_running = False
            if self.safety_thread and self.safety_thread.is_alive():
                self.safety_thread.join(timeout=1.0)
            
            # 모터 정지
            self.emergency_stop()
            
            # PWM 정리
            if self.rpi_gpio:
                self.rpi_gpio.set_servo_pulsewidth(self.config.channel, 0)
                self.rpi_gpio.stop()
            elif self.pwm:
                self.pwm.stop()
                GPIO.cleanup()
            
            self.logger.info("ESC 제어기 정리 완료")
            
        except Exception as e:
            self.logger.error(f"정리 중 오류 발생: {e}")
    
    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.cleanup()


# 사용 예제
if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # ESC 제어기 생성
    config = MotorConfig(
        channel=1,
        frequency=50,
        min_pulse_width=1000,
        max_pulse_width=2000,
        neutral_pulse_width=1500
    )
    
    with ESCController(config) as esc:
        # 상태 변화 콜백 설정
        def on_state_change(state):
            print(f"모터 상태 변경: {state.value}")
        
        def on_error(error_msg):
            print(f"오류 발생: {error_msg}")
        
        esc.on_state_change = on_state_change
        esc.on_error = on_error
        
        # ESC ARM
        if esc.arm():
            print("ESC ARM 성공")
            
            try:
                # 모터 제어 테스트
                print("모터 정방향 50% 속도로 3초간 실행...")
                esc.set_speed(0.5)
                time.sleep(3)
                
                print("모터 정지...")
                esc.stop()
                time.sleep(1)
                
                print("모터 역방향 30% 속도로 3초간 실행...")
                esc.set_speed(-0.3)
                time.sleep(3)
                
                print("모터 정지...")
                esc.stop()
                
            except KeyboardInterrupt:
                print("\n사용자에 의해 중단됨")
            finally:
                esc.emergency_stop()
        else:
            print("ESC ARM 실패")
