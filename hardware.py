# hardware.py
import asyncio
import time
import config

try:
    import busio
    from board import SCL, SDA
    from adafruit_pca9685 import PCA9685
    hardware_present = True
except ImportError:
    hardware_present = False
    print("WARNING: Hardware libraries not found. Running in simulation mode.")

# --- 내부 상태 ---
pca = None
engine_enabled = False  # "ESC 출력 채널 활성"(아밍 완료) 상태

def _us_to_duty(us: int) -> int:
    # 50Hz → 20,000us 주기, CircuitPython PCA9685는 16-bit duty_cycle(0~65535)
    return int(us / (1_000_000 / config.FREQUENCY_HZ) * config.FULL_DUTY_CYCLE)

def init():
    """PCA9685 초기화"""
    global pca
    if not hardware_present:
        return
    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c)
    pca.frequency = config.FREQUENCY_HZ
    set_safe_state()

def set_safe_state():
    """안전 상태: 조향 센터, 램프 OFF, ESC FULL-OFF(무음)"""
    if not hardware_present or pca is None:
        return
    # 조향
    center = _us_to_duty(config.STEER_CENTER_US)
    pca.channels[config.CH_STEER].duty_cycle = center
    # 램프
    pca.channels[config.CH_HEAD].duty_cycle = 0
    pca.channels[config.CH_TAIL].duty_cycle = 0
    # ESC 중립 펄스 유지 (아직 엔진이 꺼져 있어도 ESC를 깨우기 위해)
    neu = _us_to_duty(config.ESC_NEUTRAL_US + config.ESC_TRIM_US)
    pca.channels[config.CH_ESC].duty_cycle = neu

def shutdown():
    """프로세스 종료 전 호출"""
    if not hardware_present or pca is None:
        return
    set_safe_state()
    time.sleep(0.2)
    pca.deinit()

def esc_from_norm(x: float) -> int:
    """
    논리 명령(-1..1)을 물리적인 ESC PWM 신호(µs)로 변환합니다.
    데드존을 적용하여 1% 이상에서 바퀴가 굴러가도록 수정된 변환입니다.
    """
    x = max(-1.0, min(1.0, float(x)))
    neu = config.ESC_NEUTRAL_US + config.ESC_TRIM_US
    
    # 데드존 적용 - 1% 미만은 중립으로 처리
    if abs(x) < config.ESC_DEADZONE_NORM:
        return int(neu)
    
    if x > 0:
        # 전진: 데드존을 넘는 순간부터 바퀴가 굴러가기 시작
        # 1%에서 즉시 반응하도록 매핑 조정
        effective_x = (x - config.ESC_FWD_START_NORM) / (1.0 - config.ESC_FWD_START_NORM)
        effective_x = max(0.0, effective_x)  # 음수 방지
        us = neu + (config.ESC_MAX_US - neu) * effective_x
    else:
        # 후진: 데드존을 넘는 순간부터 바퀴가 굴러가기 시작
        effective_x = (-x - config.ESC_REV_START_NORM) / (1.0 - config.ESC_REV_START_NORM)
        effective_x = max(0.0, effective_x)  # 음수 방지
        us = neu - (neu - config.ESC_MIN_US) * effective_x

    return int(us)

async def set_engine_enabled_async(on: bool):
    """
    엔진 상태에 맞춰 ESC 채널 제어 (비동기).
    - True : 표준 ESC 아밍 절차 수행
    - False: ESC 채널 FULL-OFF (무음)
    """
    global engine_enabled
    if engine_enabled == on:
        return

    if not hardware_present or pca is None:
        engine_enabled = on
        return

    if on:
        print("ESC 아밍 시작...")
        
        # 1) ESC를 완전히 끄기
        pca.channels[config.CH_ESC].duty_cycle = 0
        await asyncio.sleep(0.1)
        
        # 2) 최대 펄스로 아밍 신호 전송
        max_duty = _us_to_duty(getattr(config, "ESC_ARM_MAX_US", config.ESC_MAX_US))
        pca.channels[config.CH_ESC].duty_cycle = max_duty
        await asyncio.sleep(getattr(config, "ARM_SEQUENCE_S", 0.2))
        
        # 3) 최소 펄스로 아밍 신호 전송
        min_duty = _us_to_duty(getattr(config, "ESC_ARM_MIN_US", config.ESC_MIN_US))
        pca.channels[config.CH_ESC].duty_cycle = min_duty
        await asyncio.sleep(getattr(config, "ARM_SEQUENCE_S", 0.2))
        
        # 4) 중립 펄스로 설정 (Micro ESC는 빠른 아밍 선호)
        neu = _us_to_duty(config.ESC_NEUTRAL_US + config.ESC_TRIM_US)
        pca.channels[config.CH_ESC].duty_cycle = neu
        await asyncio.sleep(getattr(config, "ARM_NEUTRAL_S", 0.5))
        
        # 5) 아밍 완료
        engine_enabled = True
        print("ESC 아밍 완료! 비프음이 들려야 합니다.")
    else:
        print("ESC 디스아밍...")
        # 디스암: ESC 채널은 중립 펄스를 유지 (ESC가 계속 깨어 있도록)
        neu = _us_to_duty(config.ESC_NEUTRAL_US + config.ESC_TRIM_US)
        pca.channels[config.CH_ESC].duty_cycle = neu
        engine_enabled = False
        print("ESC 디스아밍 완료.")

def set_steering(pulse_us: int):
    """조향 서보 제어"""
    if not hardware_present or pca is None:
        return
    pca.channels[config.CH_STEER].duty_cycle = _us_to_duty(pulse_us)

def set_esc_speed(norm: float):
    """ESC 출력 제어 (엔진 활성일 때만)"""
    if not hardware_present or pca is None:
        return
    if not engine_enabled:
        # 엔진 비활성 시에도 ESC에는 중립 펄스를 지속 출력
        neu = _us_to_duty(config.ESC_NEUTRAL_US + config.ESC_TRIM_US)
        pca.channels[config.CH_ESC].duty_cycle = neu
        return
    duty = _us_to_duty(esc_from_norm(norm))
    pca.channels[config.CH_ESC].duty_cycle = duty

def set_headlight(level: float):
    """전조등 밝기 제어"""
    if not hardware_present or pca is None:
        return
    lv = int(max(0.0, min(1.0, level)) * config.FULL_DUTY_CYCLE)
    pca.channels[config.CH_HEAD].duty_cycle = lv

def set_taillight(level: float):
    """후미등 밝기 제어"""
    if not hardware_present or pca is None:
        return
    lv = int(max(0.0, min(1.0, level)) * config.FULL_DUTY_CYCLE)
    pca.channels[config.CH_TAIL].duty_cycle = lv