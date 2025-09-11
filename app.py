from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import json
import time
import threading
import queue
import logging
import asyncio
import websockets
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp, GLib
try:
    import sdp_transform
except ImportError:
    # sdp_transform이 없으면 간단한 SDP 파싱 함수 사용
    def parse_sdp(sdp_text):
        return {'media': []}
    sdp_transform = type('sdp_transform', (), {'parse': parse_sdp})()

# GStreamer 초기화
Gst.init(None)

app = Flask(__name__)
CORS(app)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 변수
control_commands = queue.Queue()
current_status = {
    'connected': False,
    'video_resolution': '1280x720',
    'fps': 30,
    'latency': 0,
    'bitrate': 3000000
}

# WebRTC 관련 전역 변수
webrtc_clients = set()
pipeline = None
webrtcbin = None

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

# GStreamer WebRTC 함수들
def create_gstreamer_pipeline():
    """3Mbps 최적화된 GStreamer 파이프라인 생성"""
    global pipeline, webrtcbin
    
    # rpicam을 사용한 카메라 캡처 파이프라인 (3Mbps 최적화)
    pipeline_str = (
        "rpicamsrc bitrate=3000000 preview=false ! "
        "video/x-h264,width=1280,height=720,framerate=30/1,profile=high ! "
        "h264parse ! "
        "rtph264pay config-interval=1 pt=96 ! "
        "webrtcbin name=webrtcbin bundle-policy=max-bundle"
    )
    
    pipeline = Gst.parse_launch(pipeline_str)
    webrtcbin = pipeline.get_by_name('webrtcbin')
    
    # WebRTC 이벤트 연결
    webrtcbin.connect('on-negotiation-needed', on_negotiation_needed)
    webrtcbin.connect('on-ice-candidate', on_ice_candidate)
    webrtcbin.connect('notify::connection-state', on_connection_state_change)
    
    logger.info("GStreamer 파이프라인 생성 완료 (3Mbps 최적화)")

def on_negotiation_needed(element):
    """WebRTC 협상 필요 시 호출"""
    logger.info("WebRTC 협상 시작")
    
    # Offer 생성
    promise = Gst.Promise.new_with_change_callback(on_offer_created, None)
    element.emit('create-offer', None, promise)

def on_offer_created(promise, element):
    """Offer 생성 완료 시 호출"""
    reply = promise.get_reply()
    offer = reply.get_value('offer')
    
    # SDP 설정
    webrtcbin.emit('set-local-description', offer, None)
    
    # SDP를 JSON으로 변환하여 클라이언트에 전송
    sdp_text = offer.get_sdp_text()
    
    offer_data = {
        'type': 'offer',
        'sdp': sdp_text
    }
    
    logger.info("Offer 생성 완료")
    # WebSocket 클라이언트들에게 Offer 전송
    asyncio.create_task(broadcast_to_clients({
        'type': 'offer',
        'data': offer_data
    }))

def on_ice_candidate(element, mline_index, candidate):
    """ICE Candidate 생성 시 호출"""
    candidate_data = {
        'candidate': candidate,
        'sdpMLineIndex': mline_index
    }
    
    logger.info(f"ICE Candidate 생성: {candidate}")
    # WebSocket 클라이언트들에게 ICE Candidate 전송
    asyncio.create_task(broadcast_to_clients({
        'type': 'ice-candidate',
        'data': candidate_data
    }))

def on_connection_state_change(element, pspec):
    """연결 상태 변경 시 호출"""
    state = element.get_property('connection-state')
    logger.info(f"WebRTC 연결 상태: {state}")
    
    if state == GstWebRTC.WebRTCConnectionState.CONNECTED:
        current_status['connected'] = True
    else:
        current_status['connected'] = False

async def broadcast_to_clients(message):
    """모든 WebSocket 클라이언트에게 메시지 전송"""
    if webrtc_clients:
        disconnected = set()
        for client in webrtc_clients:
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        
        # 연결이 끊어진 클라이언트 제거
        webrtc_clients -= disconnected

# WebSocket 서버
async def handle_webrtc_client(websocket, path):
    """WebRTC 클라이언트 연결 처리"""
    webrtc_clients.add(websocket)
    logger.info(f"WebRTC 클라이언트 연결: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            data = json.loads(message)
            await handle_webrtc_message(data)
            
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebRTC 클라이언트 연결 종료")
    except Exception as e:
        logger.error(f"WebRTC 클라이언트 처리 오류: {e}")
    finally:
        webrtc_clients.discard(websocket)

async def handle_webrtc_message(data):
    """WebRTC 메시지 처리"""
    message_type = data.get('type')
    
    if message_type == 'answer':
        await handle_answer(data.get('data'))
    elif message_type == 'ice-candidate':
        await handle_ice_candidate(data.get('data'))
    elif message_type == 'start':
        await start_gstreamer_stream()
    elif message_type == 'stop':
        await stop_gstreamer_stream()

async def handle_answer(answer_data):
    """클라이언트 Answer 처리"""
    sdp_text = answer_data.get('sdp')
    
    # SDP 생성
    sdp = GstSdp.SDPMessage.new()
    sdp.parse_text(sdp_text)
    
    # Answer 설정
    answer = GstWebRTC.WebRTCSessionDescription.new(
        GstWebRTC.WebRTCSDPType.ANSWER, sdp
    )
    
    webrtcbin.emit('set-remote-description', answer, None)
    logger.info("Answer 설정 완료")

async def handle_ice_candidate(candidate_data):
    """클라이언트 ICE Candidate 처리"""
    candidate = candidate_data.get('candidate')
    mline_index = candidate_data.get('sdpMLineIndex', 0)
    
    # ICE Candidate 추가
    webrtcbin.emit('add-ice-candidate', mline_index, candidate)
    logger.info(f"ICE Candidate 추가: {candidate}")

async def start_gstreamer_stream():
    """GStreamer 스트림 시작"""
    global pipeline
    if pipeline:
        pipeline.set_state(Gst.State.PLAYING)
        current_status['connected'] = True
        logger.info("GStreamer 스트림 시작")

async def stop_gstreamer_stream():
    """GStreamer 스트림 중지"""
    global pipeline
    if pipeline:
        pipeline.set_state(Gst.State.NULL)
        current_status['connected'] = False
        logger.info("GStreamer 스트림 중지")

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
            # 실제 구현에서는 GStreamer에서 지연시간 정보를 가져옴
            current_status['latency'] = 50 + (time.time() % 10)  # 임시 지연시간 시뮬레이션

def run_gstreamer():
    """GStreamer 메인 루프 실행"""
    create_gstreamer_pipeline()
    
    # 파이프라인 시작
    if pipeline:
        pipeline.set_state(Gst.State.PLAYING)
        
    # GStreamer 메인 루프
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        logger.info("GStreamer 종료")
        if pipeline:
            pipeline.set_state(Gst.State.NULL)

async def start_websocket_server():
    """WebSocket 서버 시작"""
    return await websockets.serve(
        handle_webrtc_client, 
        '0.0.0.0', 
        8080
    )

def run_server():
    """통합 서버 실행"""
    # GStreamer 스레드 시작
    gst_thread = threading.Thread(target=run_gstreamer, daemon=True)
    gst_thread.start()
    
    # 상태 업데이트 스레드 시작
    status_thread = threading.Thread(target=update_status, daemon=True)
    status_thread.start()
    
    # WebSocket 서버 시작
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # WebSocket 서버 시작
        ws_server = loop.run_until_complete(start_websocket_server())
        logger.info("WebSocket 서버 시작: 0.0.0.0:8080")
        
        # Flask 서버 시작 (별도 스레드)
        flask_thread = threading.Thread(
            target=lambda: app.run(
                host='0.0.0.0',
                port=8000,
                debug=False,
                threaded=True,
                use_reloader=False
            ),
            daemon=True
        )
        flask_thread.start()
        logger.info("Flask 서버 시작: 0.0.0.0:8000")
        
        # 메인 루프 실행
        loop.run_forever()
        
    except KeyboardInterrupt:
        logger.info("서버 종료")
    finally:
        loop.close()

if __name__ == '__main__':
    run_server()
