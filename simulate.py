def map_axis_to_angle(axis: int) -> int:
    # axis -50..0..50를 ESC 각도 65..120..180으로 선형 매핑
    # 후진 최대속도 65, 중립 120, 전진 최대속도 180
    axis = max(-50, min(50, int(axis)))
    if axis >= 0:
        # 0..50 -> 120..180
        return int(120 + (axis / 50) * (180 - 120))
    else:
        # -50..0 -> 65..120
        return int(65 + ((axis + 50) / 50) * (120 - 65))