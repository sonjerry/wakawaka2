def map_axis_to_angle(axis: int, gear: str) -> int:
    """
    축 입력과 기어에 따라 ESC 각도를 결정한다.
    - D 기어: axis>0 일 때만 120..180° (전진)
      axis 0 -> 120°, axis 50 -> 180°
    - R 기어: axis>0 일 때만 120..65° (후진)
      axis 0 -> 120°, axis 50 -> 65°
    - 그 외(P/N 또는 axis<=0): 항상 중립 120°
    """
    axis = max(-50, min(50, int(axis)))
    g = (gear or '').upper()
    if axis > 0 and g == 'D':
        return int(120 + (axis / 50) * (180 - 120))
    if axis > 0 and g == 'R':
        return int(120 - (axis / 50) * (120 - 65))
    return 120