from flask import Flask, render_template
from flask_sock import Sock
import threading
import json
import time
from simulate import map_axis_to_angle
from hardware import init_hardware, set_steer_angle, set_throttle, arm_esc_sequence

app = Flask(__name__)
sock = Sock(app)

# 상태
state = {
    'engine_running': False,
    'gear': 'P',
    'head_on': False,
    'axis': 0,
    'steer_angle': 0,
    'throttle_angle': 120,
    'rpm': 0,
    'speed': 0
}

# 설정
AXIS_MIN = -50
AXIS_MAX = 50
RPM_LIMIT_PN = 4000
STEER_MIN = -66
STEER_MAX = 66
SERVO_PULSE_MIN = 1000
SERVO_PULSE_MAX = 2000

# 하드웨어 초기화 (조향 중앙, ESC 중립)
init_hardware()

def map_steer_to_pulse(angle):
    return int(SERVO_PULSE_MIN + (angle - STEER_MIN) * (SERVO_PULSE_MAX - SERVO_PULSE_MIN) / (STEER_MAX - STEER_MIN))

@app.route('/')
def index():
    return render_template('index.html')

# ===== WebSocket 구현 =====
clients = set()
clients_lock = threading.Lock()

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
    global state
    if 'ping' in msg:
        return {'type': 'pong', 'pong': msg['ping']}

    if 'engine_toggle' in msg and msg['engine_toggle']:
        if not state['engine_running'] and state['gear'] == 'P' and state['axis'] < 0:
            state['engine_running'] = True
            state['gear'] = 'P'
            threading.Thread(target=arm_esc_sequence, daemon=True).start()
            set_steer_angle(0)
            state['rpm'] = 700
            state['steer_angle'] = 0
        elif state['engine_running']:
            state['engine_running'] = False
            state['rpm'] = 700
            set_throttle(120)
            state['throttle_angle'] = 120
            set_steer_angle(0)
            state['steer_angle'] = 0
        broadcast_update({'engine_running': state['engine_running'], 'gear': state['gear'], 'rpm': state['rpm'], 'steer_angle': state['steer_angle'], 'throttle_angle': state['throttle_angle']})

    if 'head_toggle' in msg and msg['head_toggle']:
        state['head_on'] = not state['head_on']
        broadcast_update({'head_on': state['head_on']})

    if 'gear' in msg and state['engine_running'] and state['axis'] < 0:
        new_gear = msg['gear']
        if new_gear in ['P', 'R', 'N', 'D']:
            state['gear'] = new_gear
            broadcast_update({'gear': state['gear']})

    if 'steer_delta' in msg and state['engine_running']:
        state['steer_angle'] = max(STEER_MIN, min(STEER_MAX, state['steer_angle'] + msg['steer_delta']))
        set_steer_angle(state['steer_angle'])
        broadcast_update({'steer_angle': state['steer_angle']})

    if 'axis' in msg:
        state['axis'] = max(AXIS_MIN, min(AXIS_MAX, msg['axis']))
        if state['engine_running']:
            # ESC 명령은 기존 규칙 유지 (전/후진 및 크리핑)
            angle = map_axis_to_angle(state['axis'], state['gear'])
            set_throttle(angle)
            state['throttle_angle'] = angle

            # 간단 물리 모델: 목표 속도 추종 + 브레이크(음수 axis) 가중 감속
            # dt는 메시지 간격 기반(대략 70ms)
            now = time.time()
            prev = getattr(process_message_dict, '_last_axis_ts', None)
            dt = 0.07 if prev is None else max(0.001, min(0.2, now - prev))
            process_message_dict._last_axis_ts = now

            speed = float(state['speed'])
            axis = state['axis']
            gear = state['gear']

            def approach(current: float, target: float, tau: float, dt_sec: float) -> float:
                # 1차 지연 모델: dv = (target-current) * (dt/tau)
                alpha = dt_sec / max(1e-3, tau)
                if alpha > 1.0:
                    alpha = 1.0
                return current + (target - current) * alpha

            # 기어별 목표속도 및 시간상수 결정
            if gear in ['P', 'N']:
                # 공회전: 속도는 0으로 천천히 수렴, 가속 없음
                v_target = 0.0
                tau = 0.6  # 공회전 감속 상수
                speed = approach(speed, v_target, tau, dt)
                rpm = 700 if axis <= 0 else min(axis * 80, RPM_LIMIT_PN)
            elif gear == 'D':
                if axis > 5:
                    # 전진 목표 속도 (기존 스케일 유지: axis*2)
                    v_target = axis * 2.0
                    tau = 1.1  # 가속 시간상수
                    speed = approach(speed, v_target, tau, dt)
                elif -5 <= axis <= 5:
                    # 크리핑 또는 관성 유지: 낮은 속도에서 2로 수렴, 고속에서는 서서히 감속
                    v_target = 2.0 if abs(speed) < 5.0 else speed
                    tau = 1.8
                    speed = approach(speed, v_target, tau, dt)
                else:
                    # 제동: 목표 0, 브레이크 강도는 음수 axis의 크기에 비례
                    brake_strength = min(1.0, max(0.0, (abs(axis) - 5) / 45.0))  # 0..1
                    tau_brake = 0.25 + (1.0 - brake_strength) * 0.75         # 0.25..1.0
                    v_target = 0.0
                    speed = approach(speed, v_target, tau_brake, dt)
                # RPM: 전진 요청/속도에 따라 가변
                rpm = int(max(700, min(8000, 700 + max(0, axis) * 90 + abs(speed) * 8)))
                # 역주행 방지: 제동으로 0 근처 도달 시 0 클램프
                if speed < 0.1 and axis <= 0:
                    speed = 0.0
            elif gear == 'R':
                # 후진은 음수 속도 사용
                if axis > 5:
                    v_target = -axis * 1.5  # 기존 스케일 유지
                    tau = 1.1
                    speed = approach(speed, v_target, tau, dt)
                elif -5 <= axis <= 5:
                    v_target = -1.5 if abs(speed) < 3.0 else speed
                    tau = 1.8
                    speed = approach(speed, v_target, tau, dt)
                else:
                    brake_strength = min(1.0, max(0.0, (abs(axis) - 5) / 45.0))
                    tau_brake = 0.25 + (1.0 - brake_strength) * 0.75
                    v_target = 0.0
                    speed = approach(speed, v_target, tau_brake, dt)
                rpm = int(max(700, min(RPM_LIMIT_PN, 700 + max(0, axis) * 80 + abs(speed) * 6)))
                if speed > -0.1 and axis <= 0:
                    speed = 0.0
            else:
                # 안전 가드
                rpm = 700
                speed = 0.0

            state['speed'] = speed
            state['rpm'] = rpm
        else:
            # 엔진 꺼짐: 계기판은 아이들 700RPM 표시, 속도 0
            state['rpm'] = 700
            state['speed'] = 0
        broadcast_update({'axis': state['axis'], 'rpm': state['rpm'], 'speed': state['speed'], 'throttle_angle': state['throttle_angle']})

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