from flask import Flask, render_template
from flask_sock import Sock
import time
import threading
import json
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
    'rpm': 0,
    'speed': 0
}

# 설정
AXIS_MIN = -50
AXIS_MAX = 50
RPM_LIMIT_PN = 4000
STEER_MIN = -90
STEER_MAX = 90
SERVO_PULSE_MIN = 1000
SERVO_PULSE_MAX = 2000

# 하드웨어 초기화 (조향 중앙, ESC 중립)
init_hardware()

def welcome_ceremony():
    global state
    state['rpm'] = RPM_LIMIT_PN
    try:
        broadcast_update({'rpm': state['rpm']})
    except Exception:
        pass
    time.sleep(1)
    state['rpm'] = 0
    try:
        broadcast_update({'rpm': state['rpm']})
    except Exception:
        pass

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
            threading.Thread(target=welcome_ceremony, daemon=True).start()
            set_steer_angle(0)
        elif state['engine_running']:
            state['engine_running'] = False
            state['rpm'] = 0
            set_throttle(120)
            set_steer_angle(0)
        broadcast_update({'engine_running': state['engine_running'], 'gear': state['gear'], 'rpm': state['rpm']})

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
            angle = map_axis_to_angle(state['axis'])
            set_throttle(angle)
            if state['gear'] in ['P', 'N'] and state['axis'] > 0:
                state['rpm'] = min(state['axis'] * 80, RPM_LIMIT_PN)
                state['speed'] = 0
            elif state['gear'] == 'D' and state['axis'] > 0:
                state['rpm'] = min(state['axis'] * 100, 8000)
                state['speed'] = state['axis'] * 2
            elif state['gear'] == 'R' and state['axis'] > 0:
                state['rpm'] = min(state['axis'] * 80, RPM_LIMIT_PN)
                state['speed'] = -state['axis'] * 1.5
            else:
                state['rpm'] = 0
                state['speed'] = 0
                set_throttle(120)
        else:
            # 엔진이 꺼져 있어도 축 입력은 반영해 시동 조건(브레이크) 판단 가능하게 함
            state['rpm'] = 0
            state['speed'] = 0
        broadcast_update({'axis': state['axis'], 'rpm': state['rpm'], 'speed': state['speed']})

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