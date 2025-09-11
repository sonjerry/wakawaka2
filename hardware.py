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
    ★ [개선] 논리 명령(-1..1)을 물리적인 ESC PWM 신호(µs)로 변환합니다.
    - Deadzone: 입력값이 매우 작을 때 모터가 떨리는 것을 방지하기 위해 중립 신호를 보냅니다.
    - Start Threshold: Deadzone을 벗어나자마자 바로 최대 출력을 내는 대신,
      설정된 '시작 임계치'부터 출력을 시작하여 더 부드러운 제어를 가능하게 합니다.
    """
    x = max(-1.0, min(1.0, float(x)))
    neu = config.ESC_NEUTRAL_US + config.ESC_TRIM_US

    dz   = float(getattr(config, "ESC_DEADZONE_NORM", 0.02))
    s_fw = float(getattr(config, "ESC_FWD_START_NORM", 0.05)) # config.py 수정에 맞춰 기본값 변경
    s_rv = float(getattr(config, "ESC_REV_START_NORM", 0.05)) # config.py 수정에 맞춰 기본값 변경

    # 1. 데드존 처리: 입력값이 데드존 안에 있으면, 정확한 중립 펄스를 반환합니다.
    if abs(x) <= dz:
        return int(neu)

    # 2. 데드존 밖의 값을 [0, 1] 범위로 정규화합니다.
    #    예: 데드존이 0.1일 때 입력 0.5 -> (0.5-0.1)/(1-0.1) -> 0.4/0.9 -> 0.444
    if x > 0:
        # 전진 (Forward)
        t = (x - dz) / (1.0 - dz)
        t = 0.0 if t < 0 else (1.0 if t > 1.0 else t) # Clamp
        
        # 3. 정규화된 값을 실제 출력 범위 [시작임계치, 1]로 다시 스케일링합니다.
        #    이것이 실제 모터에 전달될 출력 강도가 됩니다.
        x_eff = s_fw + (1.0 - s_fw) * t
        
        # 4. 출력 강도를 실제 PWM 펄스 폭(µs)으로 변환합니다.
        #    [중립, 최대] 범위 내에서 비례적으로 계산됩니다.
        us = neu + (config.ESC_MAX_US - neu) * x_eff
    else:
        # 후진 (Reverse)
        t = ((-x) - dz) / (1.0 - dz)
        t = 0.0 if t < 0 else (1.0 if t > 1.0 else t) # Clamp
        x_eff = s_rv + (1.0 - s_rv) * t
        us = neu - (neu - config.ESC_MIN_US) * x_eff

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
        
        # 1) ESC를 완전히 끄기 (0% duty cycle)
        pca.channels[config.CH_ESC].duty_cycle = 0
        await asyncio.sleep(0.1)
        
        # 2) 최대 펄스로 아밍 신호 전송
        max_duty = _us_to_duty(getattr(config, "ESC_ARM_MAX_US", config.ESC_MAX_US))
        pca.channels[config.CH_ESC].duty_cycle = max_duty
        await asyncio.sleep(getattr(config, "ARM_SEQUENCE_S", 0.5))
        
        # 3) 최소 펄스로 아밍 신호 전송
        min_duty = _us_to_duty(getattr(config, "ESC_ARM_MIN_US", config.ESC_MIN_US))
        pca.channels[config.CH_ESC].duty_cycle = min_duty
        await asyncio.sleep(getattr(config, "ARM_SEQUENCE_S", 0.5))
        
        # 4) 중립 펄스로 설정하고 아밍 완료 대기
        neu = _us_to_duty(config.ESC_NEUTRAL_US + config.ESC_TRIM_US)
        pca.channels[config.CH_ESC].duty_cycle = neu
        print(f"ESC 중립 펄스 유지 중... ({getattr(config, 'ARM_NEUTRAL_S', 2.0)}초)")
        await asyncio.sleep(max(0.0, float(getattr(config, "ARM_NEUTRAL_S", 2.0))))
        
        # 5) 아밍 완료
        engine_enabled = True
        print("ESC 아밍 완료! 비프음이 들려야 합니다.")
        
        # 6) 안전: 중립 재주입
        pca.channels[config.CH_ESC].duty_cycle = neu
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