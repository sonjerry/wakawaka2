"""
RC Car Physics Simulation
전기차 스타일의 가속/감속 물리 시뮬레이션
"""

import time


class RCCarPhysics:
    """
    RC카 물리 시뮬레이션
    - 액셀/브레이크 분리 입력 (각각 0~50)
    - 실시간 속도 상태 유지
    - 전기차 스타일 가속/감속/크리핑
    """
    
    # 속도 제한
    MAX_SPEED_FORWARD = 20.0  # km/h (전진 최고속)
    MAX_SPEED_REVERSE = 7.0   # km/h (후진 최고속)
    
    # 크리핑
    CREEP_SPEED = 2.0  # km/h (액셀/브레이크 0일 때)
    
    # DC모터 각도 매핑
    MOTOR_NEUTRAL = 120  # 중립 (0 km/h)
    MOTOR_FORWARD_MAX = 180  # 전진 최대
    MOTOR_REVERSE_MAX = 65   # 후진 최대
    MOTOR_CREEP = 130  # 크리핑
    
    # 물리 상수 (튜닝 필요)
    # 가속: 0->20km/h 풀액셀(50)로 8초
    # 평균 가속도 = 20/8 = 2.5 km/h/s
    # 저속일수록 가속 느림 -> 가속도가 속도에 비례하도록
    ACCEL_BASE = 0.8         # 기본 가속도 (km/h/s per accel_axis unit)
    ACCEL_SPEED_FACTOR = 0.04  # 속도에 비례한 추가 가속도
    
    # 브레이크: 20km/h에서 풀브레이크(50)로 2초 정지
    # 필요 감속도 = 20/2 = 10 km/h/s
    BRAKE_BASE = 0.2         # 기본 브레이크 감속도 (km/h/s per brake_axis unit)
    
    # 관성 감속 (속도에 비례)
    # 실제 전기차: 100km/h에서 발 떼면 약 10-15초 정도 60km/h까지 감속
    # 비율로 환산: 20km/h에서 약 5-7초 정도면 10km/h까지 감속
    DRAG_COEFFICIENT = 0.15   # 속도에 비례한 저항 (km/h/s per km/h)
    
    def __init__(self):
        self.current_speed_kmh = 0.0  # 현재 속도 (항상 양수)
        self.last_update_time = time.monotonic()
    
    def reset(self):
        """시뮬레이션 초기화"""
        self.current_speed_kmh = 0.0
        self.last_update_time = time.monotonic()
    
    def update(self, accel_axis: float, brake_axis: float, gear: str) -> tuple[float, int]:
        """
        물리 시뮬레이션 업데이트
        
        Args:
            accel_axis: 액셀 페달 깊이 (0~50)
            brake_axis: 브레이크 페달 깊이 (0~50)
            gear: 현재 기어 ('P', 'R', 'N', 'D')
        
        Returns:
            (current_speed_kmh, motor_angle)
        """
        now = time.monotonic()
        dt = now - self.last_update_time
        self.last_update_time = now
        
        # dt 제한 (너무 크면 시뮬레이션 불안정)
        dt = min(dt, 0.1)
        
        # 입력 클램핑
        accel_axis = max(0.0, min(50.0, float(accel_axis)))
        brake_axis = max(0.0, min(50.0, float(brake_axis)))
        gear = (gear or '').upper()
        
        # P/N 기어: 중립, 속도 0으로 강제
        if gear in ['P', 'N']:
            self.current_speed_kmh = 0.0
            return (0.0, self.MOTOR_NEUTRAL)
        
        # D/R 기어에서만 동작
        if gear not in ['D', 'R']:
            return (self.current_speed_kmh, self.speed_to_motor_angle(self.current_speed_kmh, gear))
        
        # 최고속도 설정
        max_speed = self.MAX_SPEED_FORWARD if gear == 'D' else self.MAX_SPEED_REVERSE
        
        # === 크리핑 처리 ===
        if accel_axis == 0.0 and brake_axis == 0.0:
            # 크리핑: 2km/h로 부드럽게 수렴
            target_speed = self.CREEP_SPEED
            speed_diff = target_speed - self.current_speed_kmh
            # 지수 수렴 (타임상수 0.5초)
            self.current_speed_kmh += speed_diff * (1.0 - pow(2.71828, -dt / 0.5))
            motor_angle = self.MOTOR_CREEP
            return (self.current_speed_kmh, motor_angle)
        
        # === 크리핑에서 브레이크로 감속 ===
        if accel_axis == 0.0 and brake_axis > 0.0 and self.current_speed_kmh <= self.CREEP_SPEED:
            # 브레이크 axis에 따라 0~2km/h 선형 조절
            # brake_axis 0 -> 2km/h, brake_axis 50 -> 0km/h
            target_speed = self.CREEP_SPEED * (1.0 - brake_axis / 50.0)
            speed_diff = target_speed - self.current_speed_kmh
            self.current_speed_kmh += speed_diff * (1.0 - pow(2.71828, -dt / 0.3))
            # 모터 각도도 선형 매핑: 130도(2km/h) -> 120도(0km/h)
            motor_angle = self.MOTOR_CREEP - int((brake_axis / 50.0) * (self.MOTOR_CREEP - self.MOTOR_NEUTRAL))
            return (self.current_speed_kmh, motor_angle)
        
        # === 가속도 계산 ===
        acceleration = 0.0
        
        # 브레이크 우선 (브레이크 밟으면 액셀 무시)
        if brake_axis > 0.0:
            # 브레이크 감속도: 속도와 브레이크 axis에 비례
            # 20km/h에서 풀브레이크(50)로 2초 정지 -> 10 km/h/s
            brake_decel = brake_axis * self.BRAKE_BASE * (1.0 + self.current_speed_kmh / 20.0)
            acceleration = -brake_decel
        
        elif accel_axis > 0.0:
            # 액셀 가속도: 저속에서 낮고, 고속에서 높음
            # 가속도 = accel_axis * (기본 + 속도비례)
            # 0-20km/h 풀액셀로 8초 조건 만족하도록 튜닝
            speed_factor = 1.0 + (self.current_speed_kmh / max_speed) * self.ACCEL_SPEED_FACTOR * max_speed
            acceleration = (accel_axis / 50.0) * self.ACCEL_BASE * speed_factor
        
        # 관성 저항 (항상 적용, 속도에 비례)
        drag = -self.DRAG_COEFFICIENT * self.current_speed_kmh
        acceleration += drag
        
        # 속도 업데이트
        self.current_speed_kmh += acceleration * dt
        
        # 속도 제한
        self.current_speed_kmh = max(0.0, min(max_speed, self.current_speed_kmh))
        
        # DC모터 각도 변환
        motor_angle = self.speed_to_motor_angle(self.current_speed_kmh, gear)
        
        return (self.current_speed_kmh, motor_angle)
    
    def speed_to_motor_angle(self, speed_kmh: float, gear: str) -> int:
        """
        속도를 DC모터 각도로 변환
        
        전진(D): 0km/h=120도, 20km/h=180도
        후진(R): 0km/h=120도, 7km/h=65도
        """
        if speed_kmh <= 0.0:
            return self.MOTOR_NEUTRAL
        
        if gear == 'D':
            # 선형 매핑: 0~20 -> 120~180
            ratio = speed_kmh / self.MAX_SPEED_FORWARD
            angle = self.MOTOR_NEUTRAL + ratio * (self.MOTOR_FORWARD_MAX - self.MOTOR_NEUTRAL)
            return int(max(self.MOTOR_NEUTRAL, min(self.MOTOR_FORWARD_MAX, round(angle))))
        
        elif gear == 'R':
            # 선형 매핑: 0~7 -> 120~65
            ratio = speed_kmh / self.MAX_SPEED_REVERSE
            angle = self.MOTOR_NEUTRAL - ratio * (self.MOTOR_NEUTRAL - self.MOTOR_REVERSE_MAX)
            return int(max(self.MOTOR_REVERSE_MAX, min(self.MOTOR_NEUTRAL, round(angle))))
        
        return self.MOTOR_NEUTRAL


# 전역 인스턴스 (하나만 사용)
_physics_engine = RCCarPhysics()


def get_physics_engine() -> RCCarPhysics:
    """물리 엔진 인스턴스 가져오기"""
    return _physics_engine
