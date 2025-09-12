import RPi.GPIO as GPIO
import time
import threading
from flask import Flask, jsonify, request

class PWMController:
    def __init__(self):
        """PWM 컨트롤러 초기화"""
        # GPIO 설정
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # PWM 채널 정의
        self.channels = {
            'servo': 0,      # 서보모터 (조향모터)
            'esc': 1,        # ESC 모듈 (DC모터 구동모터)
            'headlight': 2,  # 전조등
            'taillight': 3   # 후미등
        }
        
        # PWM 객체들
        self.pwm_objects = {}
        
        # ESC 상태
        self.esc_ready = False
        self.esc_armed = False
        
        # 서보모터 중앙값 (1.5ms 펄스)
        self.servo_center = 7.5
        
        # ESC 최소/최대값
        self.esc_min = 5.0   # 정지
        self.esc_max = 10.0  # 최대 속도
        
        self.initialize_pwm()
    
    def initialize_pwm(self):
        """PWM 초기화"""
        for channel_name, channel_num in self.channels.items():
            try:
                pwm = GPIO.PWM(channel_num, 50)  # 50Hz 주파수
                pwm.start(0)  # 0% 듀티 사이클로 시작
                self.pwm_objects[channel_name] = pwm
                print(f"{channel_name} PWM 초기화 완료 (채널: {channel_num})")
            except Exception as e:
                print(f"{channel_name} PWM 초기화 실패: {e}")
                self.pwm_objects[channel_name] = None
    
    def set_servo_angle(self, angle):
        """서보모터 각도 설정 (조향모터)
        Args:
            angle: -90 ~ 90도 (음수: 좌회전, 양수: 우회전)
        """
        if not -90 <= angle <= 90:
            print("서보모터 각도는 -90도에서 90도 사이여야 합니다.")
            return
        
        if self.pwm_objects['servo'] is None:
            return
        
        # 각도를 듀티 사이클로 변환 (1ms ~ 2ms 펄스)
        # -90도: 1ms (5%), 0도: 1.5ms (7.5%), 90도: 2ms (10%)
        duty_cycle = 5 + (angle + 90) * (5 / 180)
        self.pwm_objects['servo'].ChangeDutyCycle(duty_cycle)
        print(f"서보모터 각도 설정: {angle}도 (듀티: {duty_cycle:.1f}%)")
    
    def set_esc_speed(self, speed):
        """ESC 속도 설정 (DC모터 구동모터)
        Args:
            speed: -100 ~ 100 (음수: 후진, 양수: 전진, 0: 정지)
        """
        if not -100 <= speed <= 100:
            print("ESC 속도는 -100에서 100 사이여야 합니다.")
            return
        
        if not self.esc_ready:
            print("ESC가 준비되지 않았습니다. 시동 버튼을 먼저 누르세요.")
            return
        
        if self.pwm_objects['esc'] is None:
            return
        
        # 속도를 듀티 사이클로 변환
        # -100: 5%, 0: 7.5%, 100: 10%
        duty_cycle = 7.5 + (speed * 2.5 / 100)
        self.pwm_objects['esc'].ChangeDutyCycle(duty_cycle)
        print(f"ESC 속도 설정: {speed}% (듀티: {duty_cycle:.1f}%)")
    
    def set_headlight(self, state):
        """전조등 제어
        Args:
            state: True (켜기) / False (끄기)
        """
        if self.pwm_objects['headlight'] is None:
            return
        
        duty_cycle = 10 if state else 0
        self.pwm_objects['headlight'].ChangeDutyCycle(duty_cycle)
        status = "켜짐" if state else "꺼짐"
        print(f"전조등: {status}")
    
    def set_taillight(self, state):
        """후미등 제어
        Args:
            state: True (켜기) / False (끄기)
        """
        if self.pwm_objects['taillight'] is None:
            return
        
        duty_cycle = 10 if state else 0
        self.pwm_objects['taillight'].ChangeDutyCycle(duty_cycle)
        status = "켜짐" if state else "꺼짐"
        print(f"후미등: {status}")
    
    def arm_esc(self):
        """ESC 준비 (시동)"""
        print("ESC 준비 중...")
        
        # ESC 준비 시퀀스
        def esc_arm_sequence():
            # 1. 최소값으로 설정 (1초)
            self.pwm_objects['esc'].ChangeDutyCycle(self.esc_min)
            time.sleep(1)
            
            # 2. 최대값으로 설정 (1초)
            self.pwm_objects['esc'].ChangeDutyCycle(self.esc_max)
            time.sleep(1)
            
            # 3. 중앙값으로 설정 (1초)
            self.pwm_objects['esc'].ChangeDutyCycle(7.5)
            time.sleep(1)
            
            # 4. 준비 완료
            self.esc_ready = True
            self.esc_armed = True
            print("ESC 준비 완료!")
        
        # 별도 스레드에서 실행
        arm_thread = threading.Thread(target=esc_arm_sequence)
        arm_thread.daemon = True
        arm_thread.start()
    
    def emergency_stop(self):
        """비상정지"""
        if self.pwm_objects['esc'] is not None:
            self.pwm_objects['esc'].ChangeDutyCycle(self.esc_min)
        self.set_servo_angle(0)
        self.esc_ready = False
        self.esc_armed = False
        print("비상정지 실행! 조향 중앙 복귀 완료")
    
    def cleanup(self):
        """리소스 정리"""
        for pwm in self.pwm_objects.values():
            if pwm is not None:
                pwm.stop()
        GPIO.cleanup()
        print("PWM 컨트롤러 정리 완료")

# Flask 웹 서버 설정
app = Flask(__name__)
pwm_controller = PWMController()

@app.route('/api/start_engine', methods=['POST'])
def start_engine():
    """시동 버튼 - ESC 준비"""
    try:
        pwm_controller.arm_esc()
        return jsonify({
            'success': True,
            'message': '시동 버튼이 눌렸습니다. ESC 준비 중...'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'시동 실패: {str(e)}'
        }), 500

@app.route('/api/steering', methods=['POST'])
def steering():
    """조향 제어"""
    try:
        data = request.get_json()
        angle = data.get('angle', 0)
        pwm_controller.set_servo_angle(angle)
        return jsonify({
            'success': True,
            'message': f'조향 각도: {angle}도'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'조향 제어 실패: {str(e)}'
        }), 500

@app.route('/api/throttle', methods=['POST'])
def throttle():
    """스로틀 제어"""
    try:
        data = request.get_json()
        speed = data.get('speed', 0)
        pwm_controller.set_esc_speed(speed)
        return jsonify({
            'success': True,
            'message': f'속도: {speed}%'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'스로틀 제어 실패: {str(e)}'
        }), 500

@app.route('/api/lights', methods=['POST'])
def lights():
    """조명 제어"""
    try:
        data = request.get_json()
        headlight = data.get('headlight', False)
        taillight = data.get('taillight', False)
        
        pwm_controller.set_headlight(headlight)
        pwm_controller.set_taillight(taillight)
        
        return jsonify({
            'success': True,
            'message': f'전조등: {"켜짐" if headlight else "꺼짐"}, 후미등: {"켜짐" if taillight else "꺼짐"}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'조명 제어 실패: {str(e)}'
        }), 500

@app.route('/api/emergency_stop', methods=['POST'])
def emergency_stop():
    """비상정지"""
    try:
        pwm_controller.emergency_stop()
        return jsonify({
            'success': True,
            'message': '비상정지 실행됨'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'비상정지 실패: {str(e)}'
        }), 500

@app.route('/api/status', methods=['GET'])
def status():
    """현재 상태 조회"""
    return jsonify({
        'esc_ready': pwm_controller.esc_ready,
        'esc_armed': pwm_controller.esc_armed,
        'channels': pwm_controller.channels
    })

if __name__ == '__main__':
    try:
        print("PWM 하드웨어 컨트롤러 시작...")
        print("채널 정보:")
        print("- 채널 0: 서보모터 (조향모터)")
        print("- 채널 1: ESC 모듈 (DC모터 구동모터)")
        print("- 채널 2: 전조등")
        print("- 채널 3: 후미등")
        print("\n웹 서버 시작 중...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n프로그램 종료 중...")
    finally:
        pwm_controller.cleanup()