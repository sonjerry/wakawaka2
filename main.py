from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import threading
import json
from simulate import PCA9685Mock, arm_esc, map_axis_to_pulse

app = Flask(__name__)
socketio = SocketIO(app)

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
pca = PCA9685Mock()

def welcome_ceremony():
    global state
    state['rpm'] = RPM_LIMIT_PN
    socketio.emit('update', {'rpm': state['rpm']})
    time.sleep(1)
    state['rpm'] = 0
    socketio.emit('update', {'rpm': state['rpm']})

def map_steer_to_pulse(angle):
    return int(SERVO_PULSE_MIN + (angle - STEER_MIN) * (SERVO_PULSE_MAX - SERVO_PULSE_MIN) / (STEER_MAX - STEER_MIN))

@app.route('/')
def index():
    return render_template('index.html', VIDEO_SRC='http://100.84.162.124:8889/cam')

@socketio.on('connect')
def handle_connect():
    emit('update', state)

@socketio.on('message')
def handle_message(data):
    global state
    try:
        msg = json.loads(data)
    except:
        return

    if 'ping' in msg:
        emit('pong', {'pong': msg['ping']})
        return

    if 'engine_toggle' in msg and msg['engine_toggle']:
        if not state['engine_running'] and state['gear'] == 'P' and state['axis'] < 0:
            state['engine_running'] = True
            state['gear'] = 'P'
            arm_esc()
            threading.Thread(target=welcome_ceremony, daemon=True).start()
            pca.set_pwm(0, 0, 1500)
        elif state['engine_running']:
            state['engine_running'] = False
            state['rpm'] = 0
            pca.set_pwm(1, 0, 1798)
            pca.set_pwm(0, 0, 1500)
        socketio.emit('update', {'engine_running': state['engine_running'], 'gear': state['gear'], 'rpm': state['rpm']})

    if 'head_toggle' in msg and msg['head_toggle']:
        state['head_on'] = not state['head_on']
        socketio.emit('update', {'head_on': state['head_on']})

    if 'gear' in msg and state['engine_running'] and state['axis'] < 0:
        new_gear = msg['gear']
        if new_gear in ['P', 'R', 'N', 'D']:
            state['gear'] = new_gear
            socketio.emit('update', {'gear': state['gear']})

    if 'steer_delta' in msg and state['engine_running']:
        state['steer_angle'] = max(STEER_MIN, min(STEER_MAX, state['steer_angle'] + msg['steer_delta']))
        pulse = map_steer_to_pulse(state['steer_angle'])
        pca.set_pwm(0, 0, pulse)
        socketio.emit('update', {'steer_angle': state['steer_angle']})

    if 'axis' in msg and state['engine_running']:
        state['axis'] = max(AXIS_MIN, min(AXIS_MAX, msg['axis']))
        pulse = map_axis_to_pulse(state['axis'])
        pca.set_pwm(1, 0, pulse)
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
            pca.set_pwm(1, 0, 1798)
        socketio.emit('update', {'axis': state['axis'], 'rpm': state['rpm'], 'speed': state['speed']})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)