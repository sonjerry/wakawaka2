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
    # 50Hz → 20,000us 주기, PCA9685는 12-bit duty_cycle(0~4095)
    # CircuitPython에서는 16-bit로 스케일링되지만 실제로는 12-bit 사용
    period_us = 1_000_000 / config.FREQUENCY_HZ  # 20,000us
    duty_ratio = us / period_us
    return int(duty_ratio * config.FULL_DUTY_CYCLE)

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
    # ESC FULL-OFF
    pca.channels[config.CH_ESC].duty_cycle = 0

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
        print(f"[아밍 1단계] ESC OFF - duty_cycle: 0")
        await asyncio.sleep(getattr(config, "ARM_OFF_DELAY_S", 0.5))
        
        # 2) 최대 펄스로 아밍 신호 전송
        max_us = getattr(config, "ESC_ARM_MAX_US", config.ESC_MAX_US)
        max_duty = _us_to_duty(max_us)
        pca.channels[config.CH_ESC].duty_cycle = max_duty
        print(f"[아밍 2단계] MAX 신호 - {max_us}us, duty_cycle: {max_duty}")
        await asyncio.sleep(getattr(config, "ARM_MAX_DELAY_S", 1.0))
        
        # 3) 최소 펄스로 아밍 신호 전송
        min_us = getattr(config, "ESC_ARM_MIN_US", config.ESC_MIN_US)
        min_duty = _us_to_duty(min_us)
        pca.channels[config.CH_ESC].duty_cycle = min_duty
        print(f"[아밍 3단계] MIN 신호 - {min_us}us, duty_cycle: {min_duty}")
        await asyncio.sleep(getattr(config, "ARM_MIN_DELAY_S", 1.0))
        
        # 4) 중립 펄스로 설정
        neutral_us = config.ESC_NEUTRAL_US + config.ESC_TRIM_US
        neu_duty = _us_to_duty(neutral_us)
        pca.channels[config.CH_ESC].duty_cycle = neu_duty
        print(f"[아밍 4단계] 중립 신호 - {neutral_us}us, duty_cycle: {neu_duty}")
        await asyncio.sleep(getattr(config, "ARM_NEUTRAL_DELAY_S", 1.0))
        
        # 5) 아밍 완료
        engine_enabled = True
        print("ESC 아밍 완료! 비프음이 들려야 합니다.")
        print(f"현재 ESC 설정: 중립={neutral_us}us, duty_cycle={neu_duty}")
        
        # 6) 아밍 확인을 위한 추가 검증
        await asyncio.sleep(0.5)
        current_status = get_esc_status()
        print(f"아밍 후 ESC 상태: {current_status}")
        
    else:
        print("ESC 디스아밍...")
        # 디스암: ESC 채널 FULL-OFF (무음)
        pca.channels[config.CH_ESC].duty_cycle = 0
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
        pca.channels[config.CH_ESC].duty_cycle = 0
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

def get_esc_status():
    """ESC 현재 상태 정보를 반환"""
    if not hardware_present or pca is None:
        return {"hardware_present": False, "pca_initialized": False}
    
    current_duty = pca.channels[config.CH_ESC].duty_cycle
    # duty cycle을 다시 us로 변환
    period_us = 1_000_000 / config.FREQUENCY_HZ
    current_us = int(current_duty * period_us / config.FULL_DUTY_CYCLE)
    
    return {
        "hardware_present": True,
        "pca_initialized": True,
        "engine_enabled": engine_enabled,
        "current_duty_cycle": current_duty,
        "current_pulse_us": current_us,
        "esc_channel": config.CH_ESC,
        "frequency_hz": config.FREQUENCY_HZ,
        "full_duty_cycle": config.FULL_DUTY_CYCLE
    }

def test_esc_pulse(us: int):
    """ESC에 특정 펄스 폭을 테스트로 전송"""
    if not hardware_present or pca is None:
        print(f"하드웨어가 초기화되지 않았습니다.")
        return
    
    duty = _us_to_duty(us)
    pca.channels[config.CH_ESC].duty_cycle = duty
    print(f"ESC 테스트: {us}us -> duty_cycle: {duty}")
    print(f"ESC 상태: {get_esc_status()}")