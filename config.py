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

# ESC 펄스 임계치 (표준 브러시드 ESC 범위 + 크리프)
ESC_MIN_US      = 1000 # ESC 최소값 (후진/브레이크)
ESC_NEUTRAL_US  = 1800 # ESC 중립값 (크리프 - 8% 속도)
ESC_MAX_US      = 2000 # ESC 최대값 (전진 - 최대 속도)
ESC_TRIM_US     = 0    # ESC 트림 조정값

# ESC 아밍을 위한 특별한 펄스값들 (표준 ESC 아밍 범위)
ESC_ARM_MIN_US  = 1000 # 아밍 시 최소 펄스
ESC_ARM_MAX_US  = 2000 # 아밍 시 최대 펄스

# ESC 아밍 시퀀스 타이밍 (초)
ARM_OFF_DELAY_S    = 0.5  # ESC OFF 후 대기 시간
ARM_MAX_DELAY_S    = 0.2  # MAX 신호 유지 시간
ARM_MIN_DELAY_S    = 0.2  # MIN 신호 유지 시간
ARM_NEUTRAL_DELAY_S = 0.2 # 중립 신호 유지 시간


# 논리 입력(-1..1)을 물리 ESC 펄스로 변환하기 위한 맵 (Micro ESC 최적화)
ESC_DEADZONE_NORM   = 0.005  # |명령|<=0.5%면 진짜 중립 펄스 유지 (최소 데드존)
ESC_FWD_START_NORM  = 0.01   # 전진 시작 임계 (1%에서 즉시 반응)
ESC_REV_START_NORM  = 0.01   # 후진 시작 임계 (1%에서 즉시 반응)

# ==== 3. 시뮬레이션 및 엔진/변속 설정 ====
TICK_S          = 0.01       # 시뮬레이션/제어 루프 주기 (100Hz)
ARM_NEUTRAL_S   = 0.5        # ESC 아밍을 위한 중립 펄스 유지 시간 (Micro ESC 최적화)
ARM_SEQUENCE_S  = 0.2        # 아밍 시퀀스 각 단계 간격 (더 빠르게)
LED_SINK_WIRING = True       # LED 배선 방식 (현재 사용되지 않음)

# ==== 3.1 새로운 8단 변속기 시스템 ====
# 기어비 (1단~8단)
GEAR_RATIOS = [4.00, 3.00, 2.30, 1.80, 1.40, 1.15, 1.00, 0.85]
FINAL_DRIVE = 1.0

# 기어별 토크 스케일 (1단~8단)
GEAR_TORQUE_SCALE = [1.00, 0.90, 0.80, 0.72, 0.66, 0.62, 0.60, 0.58]

# 기어별 엔진 브레이크 드래그 스케일 (1단~8단)
GEAR_DRAG_SCALE = [1.00, 0.75, 0.55, 0.40, 0.30, 0.22, 0.16, 0.12]

# vRPM 설정
VRPM_IDLE = 700
VRPM_RED = 7000
VRPM_UP_THRESHOLD = 6300      # 업시프트 임계값
VRPM_DOWN_THRESHOLD = 2100    # 다운시프트 임계값
VRPM_CUT_HYSTERESIS = 200     # 레드라인 컷 히스테리시스

# 속도 추정기 파라미터 (센서 없을 때)
SPEED_ESTIMATOR_GAMMA = 0.05  # 속도 추정기 감쇠 계수
WHEEL_RADIUS = 0.3           # 바퀴 반지름 (미터)

# ==== 3.2 변속 상태기계 파라미터 ====
# 변속 이벤트 타임라인 (100Hz 기준)
SHIFT_PRECUT_MS = 30         # PRECUT 단계 시간
SHIFT_CUT_HOLD_MS = 90       # CUT_HOLD 단계 시간  
SHIFT_REENGAGE_MS = 180      # REENGAGE 단계 시간
SHIFT_JERK_MS = 30           # JERK 단계 시간
SHIFT_STABILIZE_MS = 50      # STABILIZE 단계 시간

# 변속 토크 제어
SHIFT_PRECUT_ALPHA = 0.4     # PRECUT 단계 토크 감소율
SHIFT_CUT_TORQUE = 4.0       # CUT_HOLD 단계 토크 (%)
SHIFT_JERK_DELTA = 5.0       # JERK 단계 토크 증가량 (%)

# ==== 3.3 토크 제어 파라미터 ====
MAX_BRAKE_TORQUE = 60.0      # 최대 브레이크 토크 (%)
MAX_DRAG_TORQUE = 20.0       # 최대 엔진 브레이크 토크 (%)
CREEP_TORQUE = 7.0           # 크리프 토크 (%)
CREEP_RELEASE_SPEED = 1.0    # 크리프 해제 속도 (m/s)

# ==== 3.4 입력 처리 파라미터 ====
INPUT_DEADZONE = 2.0         # 입력 데드존
INPUT_SLEW_LIMIT = 10.0      # 입력 슬루 제한 (루프당)
THROTTLE_DELAY_RPM = 200     # 스로틀 높을 때 업시프트 지연 허용 RPM

# ==== 3.5 RPM 스케일링 (UI용) ====
RPM_SCALE_MAX = 8000.0  # UI에서 사용하는 최대 RPM 값

CRANKING_DURATION_S = 0.8    # 시동 거는 시간

# ==== 4. 입력/기타 설정 ====
AXIS_DEADZONE_UNITS = 5.0    # 입력 축 데드존 (±5)

# 조향/시동 정책
ALLOW_STEER_WHEN_ENGINE_ON = True
ENGINE_STOP_REQUIRE_P = True
ENGINE_STOP_HINT_KO = "P 모드로 옮기세요!"
ENGINE_STOP_HINT_EN = "Move the lever to P to stop the engine."

# 스트리밍
VIDEO_IFRAME_SRC = "http://100.84.162.124:8889/cam"