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
    - 전기차 스타일: 액셀 = 모터 출력, 브레이크 = 회생 제동
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
    
    # 물리 상수
    # 브레이크: 20km/h에서 풀브레이크(50)로 2초 정지
    # 필요 감속도 = 20/2 = 10 km/h/s → 50 axis당 10 → axis당 0.2
    BRAKE_DECEL_PER_AXIS = 0.2  # km/h/s per brake_axis unit
    
    # 관성 감속 (속도에 비례)
    # 20km/h에서 약 6-7초 만에 정지
    DRAG_COEFFICIENT = 0.5  # 속도에 비례한 저항
    
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
        
        실제 전기차 방식:
        - 액셀 페달 → 모터 출력 (각도) 직접 제어
        - 모터 출력 → 가속력 발생
        - 브레이크 → 회생 제동 (감속)
        
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
            return (self.current_speed_kmh, self.MOTOR_NEUTRAL)
        
        # 최고속도 설정
        max_speed = self.MAX_SPEED_FORWARD if gear == 'D' else self.MAX_SPEED_REVERSE
        
        # === 크리핑 처리 ===
        CREEP_THRESHOLD = 1.0  # axis 값이 1 미만이면 크리핑으로 간주
        CREEP_SPEED_THRESHOLD = 5.0  # 5km/h 이하에서만 크리핑 작동
        
        if accel_axis < CREEP_THRESHOLD and brake_axis < CREEP_THRESHOLD and self.current_speed_kmh < CREEP_SPEED_THRESHOLD:
            # 크리핑: 2km/h로 빠르게 수렴 (1초 안에 도달)
            target_speed = self.CREEP_SPEED
            speed_diff = target_speed - self.current_speed_kmh
            alpha = 1.0 - pow(2.71828, -dt / 0.15)
            self.current_speed_kmh += speed_diff * alpha
            
            if abs(self.current_speed_kmh - target_speed) < 0.1:
                self.current_speed_kmh = target_speed
            
            return (self.current_speed_kmh, self.MOTOR_CREEP)
        
        # === 크리핑에서 브레이크로 감속 ===
        if accel_axis < CREEP_THRESHOLD and brake_axis >= CREEP_THRESHOLD and self.current_speed_kmh <= self.CREEP_SPEED * 1.2:
            target_speed = self.CREEP_SPEED * (1.0 - brake_axis / 50.0)
            speed_diff = target_speed - self.current_speed_kmh
            alpha = 1.0 - pow(2.71828, -dt / 0.15)
            self.current_speed_kmh += speed_diff * alpha
            
            if abs(self.current_speed_kmh - target_speed) < 0.05:
                self.current_speed_kmh = target_speed
            
            motor_angle = self.MOTOR_CREEP - int((brake_axis / 50.0) * (self.MOTOR_CREEP - self.MOTOR_NEUTRAL))
            return (self.current_speed_kmh, motor_angle)
        
        # === 모터 각도 및 가속도 계산 ===
        motor_angle = self.MOTOR_NEUTRAL
        acceleration = 0.0
        accel_ratio = accel_axis / 50.0  # 0~1
        
        if brake_axis > 0.0:
            # 브레이크: 중립 각도 + 감속
            motor_angle = self.MOTOR_NEUTRAL
            brake_decel = brake_axis * self.BRAKE_DECEL_PER_AXIS
            acceleration = -brake_decel
        
        elif accel_axis > 0.0:
            # 액셀: 페달 입력에 비례한 모터 각도
            if gear == 'D':
                # 전진: 120~180도
                motor_angle = int(self.MOTOR_NEUTRAL + accel_ratio * (self.MOTOR_FORWARD_MAX - self.MOTOR_NEUTRAL))
            else:  # gear == 'R'
                # 후진: 120~65도
                motor_angle = int(self.MOTOR_NEUTRAL - accel_ratio * (self.MOTOR_NEUTRAL - self.MOTOR_REVERSE_MAX))
            
            # 모터 출력에 따른 가속력
            # 목표: 풀액셀로 0->20km/h 5초
            # 평균 가속도 = 20/5 = 4 km/h/s
            # 초기 가속도를 더 높게 설정하여 평균 4를 맞춤
            base_accel = 6.0  # km/h/s at 풀파워
            
            # 속도가 높아질수록 가속력 감소 (저항 증가)
            speed_factor = max(0.1, 1.0 - (self.current_speed_kmh / max_speed) * 0.7)
            
            acceleration = accel_ratio * base_accel * speed_factor
        
        else:
            # 둘 다 안 밟음: 중립 각도, 관성만
            motor_angle = self.MOTOR_NEUTRAL
        
        # 관성 저항 (항상 적용, 속도에 비례)
        drag = -self.DRAG_COEFFICIENT * self.current_speed_kmh
        acceleration += drag
        
        # 속도 업데이트
        self.current_speed_kmh += acceleration * dt
        
        # 속도 제한
        self.current_speed_kmh = max(0.0, min(max_speed, self.current_speed_kmh))
        
        return (self.current_speed_kmh, motor_angle)


# 전역 인스턴스 (하나만 사용)
_physics_engine = RCCarPhysics()


def get_physics_engine() -> RCCarPhysics:
    """물리 엔진 인스턴스 가져오기"""
    return _physics_engine
