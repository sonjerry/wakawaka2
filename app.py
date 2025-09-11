from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import json
import time
import threading
import queue
import logging
import subprocess
import os
import signal

app = Flask(__name__)
CORS(app)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 변수
control_commands = queue.Queue()
current_status = {
    'connected': False,
    'video_resolution': '854x480',
    'fps': 24,
    'latency': 0,
    'bitrate': 3000000
}

# FFmpeg + MediaMTX 관련 전역 변수
ffmpeg_process = None
mediamtx_process = None

@app.route('/')
def index():
    """메인 페이지"""
    return app.send_static_file('index.html')

@app.route('/api/status')
def get_status():
    """연결 상태 조회"""
    return jsonify(current_status)

@app.route('/api/control', methods=['POST'])
def control():
    """RC카 제어 명령"""
    try:
        data = request.get_json()
        command = data.get('command')
        action = data.get('action')
        timestamp = data.get('timestamp', time.time())
        
        # 명령 처리
        control_data = {
            'command': command,
            'action': action,
            'timestamp': timestamp
        }
        
        control_commands.put(control_data)
        logger.info(f"제어 명령 수신: {command} {action}")
        
        return jsonify({'status': 'success', 'message': '명령이 전송되었습니다'})
    
    except Exception as e:
        logger.error(f"제어 명령 오류: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

def start_ffmpeg_stream():
    """FFmpeg으로 카메라 스트림 시작"""
    global ffmpeg_process
    
    try:
        # FFmpeg 명령어 (rpicam + H.264 + RTMP)
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'v4l2',  # Video4Linux2 입력
            '-video_size', '1280x720',
            '-framerate', '30',
            '-i', '/dev/video0',  # 카메라 장치
            '-c:v', 'libx264',  # H.264 인코딩
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-b:v', '3M',
            '-maxrate', '3M',
            '-bufsize', '6M',
            '-f', 'flv',  # FLV 출력 포맷
            'rtmp://localhost:1935/live/stream'  # MediaMTX RTMP 엔드포인트
        ]
        
        logger.info("FFmpeg 스트림 시작")
        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        current_status['connected'] = True
        logger.info("FFmpeg 스트림 시작됨")
        
    except Exception as e:
        logger.error(f"FFmpeg 시작 오류: {e}")
        current_status['connected'] = False

def stop_ffmpeg_stream():
    """FFmpeg 스트림 중지"""
    global ffmpeg_process
    
    try:
        if ffmpeg_process:
            os.killpg(os.getpgid(ffmpeg_process.pid), signal.SIGTERM)
            ffmpeg_process.wait(timeout=5)
            ffmpeg_process = None
            
        current_status['connected'] = False
        logger.info("FFmpeg 스트림 중지됨")
        
    except Exception as e:
        logger.error(f"FFmpeg 중지 오류: {e}")

def start_mediamtx():
    """MediaMTX 서버 시작"""
    global mediamtx_process
    
    try:
        # MediaMTX 설정 파일 생성
        config = """
# MediaMTX 설정
rtmp: yes
rtsp: yes
webrtc: yes
hls: no
webrtcEncryption: no
webrtcAllowOrigin: "*"
logLevel: info
logDestinations: [stdout]
rtmpAddress: ":1935"
rtspAddress: ":8554"
webrtcAddress: ":8889"
apiAddress: ":9997"
metricsAddress: ":9998"
pprofAddress: ":9999"
"""
        
        with open('mediamtx.yml', 'w') as f:
            f.write(config)
        
        # MediaMTX 실행
        mediamtx_cmd = ['/usr/local/bin/mediamtx', 'mediamtx.yml']
        
        logger.info("MediaMTX 서버 시작")
        mediamtx_process = subprocess.Popen(
            mediamtx_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # MediaMTX 시작 대기
        time.sleep(3)
        
        # MediaMTX 상태 확인
        if mediamtx_process.poll() is None:
            logger.info("MediaMTX 서버 시작됨")
        else:
            logger.error("MediaMTX 서버 시작 실패")
            raise Exception("MediaMTX 서버 시작 실패")
        
    except Exception as e:
        logger.error(f"MediaMTX 시작 오류: {e}")
        raise

def stop_mediamtx():
    """MediaMTX 서버 중지"""
    global mediamtx_process
    
    try:
        if mediamtx_process:
            os.killpg(os.getpgid(mediamtx_process.pid), signal.SIGTERM)
            mediamtx_process.wait(timeout=5)
            mediamtx_process = None
            
        logger.info("MediaMTX 서버 중지됨")
        
    except Exception as e:
        logger.error(f"MediaMTX 중지 오류: {e}")

@app.route('/api/stream/start', methods=['POST'])
def start_stream():
    """스트림 시작"""
    try:
        # FFmpeg 스트림 시작 (MediaMTX는 스크립트에서 실행됨)
        start_ffmpeg_stream()
        
        return jsonify({
            'status': 'success', 
            'message': '스트림이 시작되었습니다',
            'rtmp_url': 'rtmp://100.84.162.124:1935/live/stream',
            'webrtc_url': 'http://100.84.162.124:8889/whep'
        })
    
    except Exception as e:
        logger.error(f"스트림 시작 오류: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/stream/stop', methods=['POST'])
def stop_stream():
    """스트림 중지"""
    try:
        stop_ffmpeg_stream()
        
        return jsonify({'status': 'success', 'message': '스트림이 중지되었습니다'})
    
    except Exception as e:
        logger.error(f"스트림 중지 오류: {e}")
        return jsonify({'error': str(e)}), 400

def get_control_command():
    """제어 명령 큐에서 명령 가져오기"""
    try:
        return control_commands.get_nowait()
    except queue.Empty:
        return None

def update_status():
    """상태 업데이트 (주기적)"""
    while True:
        time.sleep(1)
        if current_status['connected']:
            # 실제 구현에서는 FFmpeg에서 지연시간 정보를 가져옴
            current_status['latency'] = 50 + (time.time() % 10)  # 임시 지연시간 시뮬레이션

def cleanup():
    """프로세스 정리"""
    stop_ffmpeg_stream()

if __name__ == '__main__':
    # 상태 업데이트 스레드 시작
    status_thread = threading.Thread(target=update_status, daemon=True)
    status_thread.start()
    
    # 종료 시 정리
    import atexit
    atexit.register(cleanup)
    
    try:
        # Flask 서버 시작
        app.run(
            host='0.0.0.0',
            port=8000,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("서버 종료")
        cleanup()