import math


def map_axis_to_angle(axis: int, gear: str) -> int:
    """
    축 입력과 기어에 따라 ESC 각도를 결정한다.
    - D 기어: axis>0 일 때만 120..180° (전진)
      axis 0 -> 120°, axis 50 -> 180°
    - R 기어: axis>0 일 때만 120..65° (후진)
      axis 0 -> 120°, axis 50 -> 65°
    - 크리핑: (D에서) axis -5..+5 이면 130° 고정 출력
    - 그 외(P/N 또는 조건 불충족): 항상 중립 120°
    """
    axis = max(-50, min(50, int(axis)))
    g = (gear or '').upper()
    # Creeping deadzone
    if g == 'D' and -5 <= axis <= 5:
        return 130
    if g == 'D' and axis > 5:
        # 5..50  -> 130..180 선형 매핑
        return int(130 + ((axis - 5) / (50 - 5)) * (180 - 130))
    if axis > 0 and g == 'R':
        return int(120 - (axis / 50) * (120 - 65))
    return 120


def _approach(current: float, target: float, tau: float, dt_sec: float) -> float:
    """
    1차 지연 모델: dv = (target-current) * (dt/tau)
    """
    alpha = dt_sec / max(1e-3, tau)
    if alpha > 1.0:
        alpha = 1.0
    return current + (target - current) * alpha


def update_speed_rpm(speed: float, axis: int, gear: str, dt: float, rpm_limit_pn: int = 4000) -> tuple[float, int]:
    """
    단순 물리 모델 기반 속도/RPM 업데이트.

    - D: 가속/관성(지수감쇠+크리핑)/브레이크(축 크기 비례)
    - R: 기존 로직 유지(간단 목표속도 추종/크리핑/브레이크)
    - P/N: 0으로 서서히 수렴

    반환: (new_speed, new_rpm)
    """
    speed_f = float(speed)
    axis_i = max(-50, min(50, int(axis)))
    g = (gear or '').upper()

    if g in ['P', 'N']:
        v_target = 0.0
        tau = 0.6
        speed_f = _approach(speed_f, v_target, tau, dt)
        rpm = 700 if axis_i <= 0 else min(axis_i * 80, rpm_limit_pn)
        return speed_f, int(rpm)

    if g == 'D':
        if axis_i > 5:
            v_target = axis_i * 2.0
            tau = 1.1
            speed_f = _approach(speed_f, v_target, tau, dt)
        elif -5 <= axis_i <= 5:
            tau_coast = 2.0
            speed_f = float(speed_f) * math.exp(-dt / max(1e-3, tau_coast))
            if abs(speed_f) < 5.0:
                speed_f = max(speed_f, 2.0)
        else:
            brake_strength = min(1.0, max(0.0, (abs(axis_i) - 5) / 45.0))
            tau_brake = 0.25 + (1.0 - brake_strength) * 0.75
            v_target = 0.0
            speed_f = _approach(speed_f, v_target, tau_brake, dt)

        rpm = int(max(700, min(8000, 700 + max(0, axis_i) * 90 + abs(speed_f) * 8)))
        if speed_f < 0.1 and axis_i <= 0:
            speed_f = 0.0
        return speed_f, rpm

    if g == 'R':
        if axis_i > 5:
            v_target = -axis_i * 1.5
            tau = 1.1
            speed_f = _approach(speed_f, v_target, tau, dt)
        elif -5 <= axis_i <= 5:
            v_target = -1.5 if abs(speed_f) < 3.0 else speed_f
            tau = 1.8
            speed_f = _approach(speed_f, v_target, tau, dt)
        else:
            brake_strength = min(1.0, max(0.0, (abs(axis_i) - 5) / 45.0))
            tau_brake = 0.25 + (1.0 - brake_strength) * 0.75
            v_target = 0.0
            speed_f = _approach(speed_f, v_target, tau_brake, dt)

        rpm = int(max(700, min(rpm_limit_pn, 700 + max(0, axis_i) * 80 + abs(speed_f) * 6)))
        if speed_f > -0.1 and axis_i <= 0:
            speed_f = 0.0
        return speed_f, rpm

    # 안전 가드
    return 0.0, 700