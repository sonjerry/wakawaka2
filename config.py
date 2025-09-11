# ==== 1. 하드웨어 채널 및 PWM 설정 ====
# PCA9685 채널 매핑
CH_STEER = 0
CH_ESC   = 1
CH_HEAD  = 3
CH_TAIL  = 4

# PWM 기본 주파수 및 듀티 사이클
FREQUENCY_HZ    = 50
FULL_DUTY_CYCLE = 65535

# ==== 2. 조향 및 ESC 서보 설정 ====
STEER_LEFT_US   = 600
STEER_RIGHT_US  = 2400
STEER_CENTER_US = 1800
STEER_SPEED_US_PER_S = 1000.0

# ESC 펄스 임계치 (대부분 1000/1500/2000µs)
ESC_MIN_US      = 1000 # 일반적인 ESC 최소값
ESC_NEUTRAL_US  = 1500 # 일반적인 ESC 중립값
ESC_MAX_US      = 2000 # 일반적인 ESC 최대값
ESC_TRIM_US     = 0    # ESC 트림 조정값

# ESC 아밍을 위한 특별한 펄스값들
ESC_ARM_MIN_US  = 1000  # 아밍 시 최소 펄스 (일부 ESC는 1100 필요)
ESC_ARM_MAX_US  = 2000  # 아밍 시 최대 펄스 (일부 ESC는 1900 필요)

# ESC 모델별 대안 설정 (주석 해제하여 사용)
# BLHeli ESC (일반적인 드론 ESC)
# ESC_ARM_MIN_US  = 1100
# ESC_ARM_MAX_US  = 1900
# ARM_NEUTRAL_S   = 3.0

# SimonK ESC (고전적인 드론 ESC)
# ESC_ARM_MIN_US  = 1000
# ESC_ARM_MAX_US  = 2000
# ARM_NEUTRAL_S   = 2.0

# 일부 RC카 ESC
# ESC_ARM_MIN_US  = 1000
# ESC_ARM_MAX_US  = 2000
# ARM_NEUTRAL_S   = 1.5

# 논리 입력(-1..1)을 물리 ESC 펄스로 변환하기 위한 맵
ESC_DEADZONE_NORM   = 0.01   # |명령|<=1%면 진짜 중립 펄스 유지
ESC_FWD_START_NORM  = 0.02   # 전진 시작 임계 (더 낮게 조정)
ESC_REV_START_NORM  = 0.02   # 후진 시작 임계 (더 낮게 조정)

# ==== 3. 시뮬레이션 및 엔진/변속 설정 ====
TICK_S          = 0.01       # 시뮬레이션/제어 루프 주기
ARM_NEUTRAL_S   = 2.0        # ESC 아밍을 위한 중립 펄스 유지 시간 (2초로 증가)
ARM_SEQUENCE_S  = 0.5        # 아밍 시퀀스 각 단계 간격
LED_SINK_WIRING = True       # LED 배선 방식 (현재 사용되지 않음)

# 가상 엔진/변속 관련
RPM_SCALE_MAX       = 8000.0
RPM_IDLE_VALUE      = 700
RPM_CREEP_VALUE     = 1100.0
RPM_FUEL_CUT_VALUE  = 7000.0
REVERSE_RPM_MAX_VALUE = 4000.0

SHIFT_DURATION_S    = 0.25     # 변속 시뮬레이션 시간 (토크컷)
SHIFT_HYSTERESIS_PCT = 4.0     # 변속 헌팅 방지용 히스테리시스 (%)
CRANKING_DURATION_S = 0.8    # 시동 거는 시간
ENGINE_INERTIA      = 0.28   # 가상 엔진의 관성

# ==== 4. 입력/기타 설정 ====
AXIS_DEADZONE_UNITS = 5.0    # 입력 축 데드존 (±5)

# 조향/시동 정책
ALLOW_STEER_WHEN_ENGINE_ON = True
ENGINE_STOP_REQUIRE_P = True
ENGINE_STOP_HINT_KO = "P 모드로 옮기세요!"
ENGINE_STOP_HINT_EN = "Move the lever to P to stop the engine."

# 스트리밍
VIDEO_IFRAME_SRC = "http://100.84.162.124:8889/cam"