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
