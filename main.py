from flask import Flask, render_template
from flask_sock import Sock
import threading
import json
import time
from simulate import get_physics_engine
from hardware import (
    init_hardware, set_steer_angle, set_throttle, arm_esc_sequence, set_led,
    STEER_MIN, STEER_MAX, SERVO_PULSE_MIN, SERVO_PULSE_MAX
)

app = Flask(__name__)
sock = Sock(app)

# 물리 엔진 인스턴스
physics = get_physics_engine()

# 입력 범위
ACCEL_MIN = 0
ACCEL_MAX = 50
BRAKE_MIN = 0
BRAKE_MAX = 50

# 상태
state = {
    'engine_running': False,
    'gear': 'P',
    'head_on': False,
    'accel_axis': 0,
    'brake_axis': 0,
    'steer_angle': 0,
    'throttle_angle': 120,
    'current_speed_kmh': 0.0,
}

# 하드웨어 초기화 (조향 중앙, ESC 중립)
init_hardware()

@app.route('/')
def index():
    return render_template('index.html')

# ===== WebSocket 구현 =====
clients = set()
clients_lock = threading.Lock()

# 최근 조향 입력 시간(자동 복귀 지연 판단용)
last_steer_input_at = 0.0

def steer_auto_center_loop():
    """차량 주행 중 일정 시간 입력이 없으면 조향각을 0으로 서서히 복귀."""
    prev = time.monotonic()
    last_broadcast_at = 0.0
    while True:
        now = time.monotonic()
        dt = max(0.0, min(0.1, now - prev))
        prev = now
        try:
            # 엔진 플래그와 무관하게, 실제 주행 상태(쓰로틀/기어)에 따라 복귀
            t = float(state['throttle_angle'])
            g = state['gear']
            factor = 0.0  # 0..1
            # 전진: 130..180, 후진: 120..65 (후진 데드존 2도)
            if g == 'D':
                factor = max(0.0, min(1.0, (t - 130.0) / (180.0 - 130.0)))
                # 크리핑(≈130°)에서도 완만히 복귀
                if t >= 130.0:
                    factor = max(factor, 0.25)
            elif g == 'R':
                R_DEAD = 2.0
                effective_start = 120.0 - R_DEAD  # 118.0
                if t < effective_start:
                    clamped = max(65.0, min(effective_start, t))
                    factor = (effective_start - clamped) / (effective_start - 65.0)
                    factor = max(factor, 0.25)  # 후진 크리핑에서도 완만히 복귀
                else:
                    factor = 0.0

            # 최근 조향 입력 150ms 이후, 주행 계수>0일 때만 복귀
            if factor > 0.0 and (now - last_steer_input_at) > 0.150:
                current = float(state['steer_angle'])
                if current != 0.0:
                    return_rate_deg_per_s = 10.0 + 70.0 * factor
                    step = return_rate_deg_per_s * dt
                    if abs(current) <= step:
                        current = 0.0
                    else:
                        current += (-step if current > 0.0 else step)
                    new_angle = int(max(STEER_MIN, min(STEER_MAX, round(current))))
                    if new_angle != state['steer_angle']:
                        state['steer_angle'] = new_angle
                        set_steer_angle(state['steer_angle'])
                        # 전송 과도 방지: 최소 60ms 간격
                        if (now - last_broadcast_at) > 0.060:
                            broadcast_update({'steer_angle': state['steer_angle']})
                            last_broadcast_at = now
        except Exception:
            pass
        time.sleep(0.02)

# 물리 시뮬레이션 루프 (20ms 주기)
def physics_simulation_loop():
    """물리 시뮬레이션 및 모터 제어 루프"""
    last_broadcast_at = 0.0
    while True:
        try:
            # 물리 엔진 업데이트
            speed_kmh, motor_angle = physics.update(
                state['accel_axis'],
                state['brake_axis'],
                state['gear']
            )
            
            # 상태 업데이트
            state['current_speed_kmh'] = speed_kmh
            state['throttle_angle'] = motor_angle
            
            # 모터 제어
            set_throttle(motor_angle)
            
            # 주기적으로 클라이언트에게 브로드캐스트 (100ms마다)
            now = time.monotonic()
            if (now - last_broadcast_at) > 0.1:
                broadcast_update({
                    'throttle_angle': state['throttle_angle'],
                    'current_speed_kmh': round(state['current_speed_kmh'], 1)
                })
                last_broadcast_at = now
        except Exception as e:
            print(f"Physics loop error: {e}")
            pass
        
        time.sleep(0.02)  # 20ms (50Hz)

# 백그라운드 스레드 시작
threading.Thread(target=steer_auto_center_loop, daemon=True).start()
threading.Thread(target=physics_simulation_loop, daemon=True).start()

def broadcast_update(payload: dict):
    message = json.dumps({'type': 'update', **payload})
    with clients_lock:
        for ws in list(clients):
            try:
                ws.send(message)
            except Exception:
                try:
                    clients.remove(ws)
                except Exception:
                    pass

def process_message_dict(msg: dict):
    global state, last_steer_input_at
    if 'ping' in msg:
        return {'type': 'pong', 'pong': msg['ping']}

    # 엔진 토글 개념 제거 (테슬라 스타일)
    if 'engine_toggle' in msg and msg['engine_toggle']:
        return None

    if 'head_toggle' in msg and msg['head_toggle']:
        state['head_on'] = not state['head_on']
        set_led(state['head_on'])  # 실제 LED 하드웨어 제어
        broadcast_update({'head_on': state['head_on']})

    # 기어 변경: 정지 상태 + 브레이크 밟음
    if 'gear' in msg:
        new_gear = msg['gear']
        if new_gear in ['P', 'R', 'N', 'D']:
            # 조건: 속도가 0이고 브레이크를 밟고 있어야 함
            if state['current_speed_kmh'] <= 0.1 and state['brake_axis'] > 0:
                state['gear'] = new_gear
                broadcast_update({'gear': state['gear']})

    # 조향 입력 (절대값 또는 delta 둘 다 지원)
    if 'steer_angle' in msg:
        # 절대값 방식 (레이싱 휠)
        state['steer_angle'] = max(STEER_MIN, min(STEER_MAX, msg['steer_angle']))
        set_steer_angle(state['steer_angle'])
        broadcast_update({'steer_angle': state['steer_angle']})
        last_steer_input_at = time.monotonic()
    elif 'steer_delta' in msg:
        # Delta 방식 (키보드)
        state['steer_angle'] = max(STEER_MIN, min(STEER_MAX, state['steer_angle'] + msg['steer_delta']))
        set_steer_angle(state['steer_angle'])
        broadcast_update({'steer_angle': state['steer_angle']})
        last_steer_input_at = time.monotonic()

    # 액셀 입력
    if 'accel_axis' in msg:
        state['accel_axis'] = max(ACCEL_MIN, min(ACCEL_MAX, msg['accel_axis']))
        broadcast_update({'accel_axis': state['accel_axis']})
    
    # 브레이크 입력
    if 'brake_axis' in msg:
        state['brake_axis'] = max(BRAKE_MIN, min(BRAKE_MAX, msg['brake_axis']))
        broadcast_update({'brake_axis': state['brake_axis']})

    return None

@sock.route('/ws')
def ws(ws):
    with clients_lock:
        clients.add(ws)
    try:
        ws.send(json.dumps({'type': 'update', **state}))
        while True:
            data = ws.receive()
            if data is None:
                break
            try:
                msg = json.loads(data)
            except Exception:
                continue
            resp = process_message_dict(msg)
            if resp is not None:
                try:
                    ws.send(json.dumps(resp))
                except Exception:
                    pass
    finally:
        with clients_lock:
            if ws in clients:
                clients.remove(ws)

# Arming은 hardware.py의 arm_esc_sequence 사용

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)