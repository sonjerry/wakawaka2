#!/usr/bin/env python3

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp, GLib
import json
import asyncio
import websockets
import threading
import logging
import base64
import sdp_transform

# GStreamer 초기화
Gst.init(None)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebRTCServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.pipeline = None
        self.webrtcbin = None
        self.loop = None
        self.websocket_server = None
        
    def create_pipeline(self):
        """rpicam을 사용한 GStreamer 파이프라인 생성"""
        # rpicam을 사용한 카메라 캡처 파이프라인
        pipeline_str = (
            "rpicamsrc bitrate=2000000 preview=false ! "
            "video/x-h264,width=1280,height=720,framerate=30/1 ! "
            "h264parse ! "
            "rtph264pay config-interval=1 pt=96 ! "
            "webrtcbin name=webrtcbin bundle-policy=max-bundle"
        )
        
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.webrtcbin = self.pipeline.get_by_name('webrtcbin')
        
        # WebRTC 이벤트 연결
        self.webrtcbin.connect('on-negotiation-needed', self.on_negotiation_needed)
        self.webrtcbin.connect('on-ice-candidate', self.on_ice_candidate)
        self.webrtcbin.connect('notify::connection-state', self.on_connection_state_change)
        
        logger.info("GStreamer 파이프라인 생성 완료")
        
    def on_negotiation_needed(self, element):
        """WebRTC 협상 필요 시 호출"""
        logger.info("WebRTC 협상 시작")
        
        # Offer 생성
        promise = Gst.Promise.new_with_change_callback(self.on_offer_created, None)
        element.emit('create-offer', None, promise)
        
    def on_offer_created(self, promise, element):
        """Offer 생성 완료 시 호출"""
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        
        # SDP 설정
        self.webrtcbin.emit('set-local-description', offer, None)
        
        # SDP를 JSON으로 변환하여 클라이언트에 전송
        sdp_text = offer.get_sdp_text()
        sdp_dict = sdp_transform.parse(sdp_text)
        
        offer_data = {
            'type': 'offer',
            'sdp': sdp_text
        }
        
        logger.info("Offer 생성 완료")
        self.send_offer_to_client(offer_data)
        
    def on_ice_candidate(self, element, mline_index, candidate):
        """ICE Candidate 생성 시 호출"""
        candidate_data = {
            'candidate': candidate,
            'sdpMLineIndex': mline_index
        }
        
        logger.info(f"ICE Candidate 생성: {candidate}")
        self.send_ice_candidate_to_client(candidate_data)
        
    def on_connection_state_change(self, element, pspec):
        """연결 상태 변경 시 호출"""
        state = element.get_property('connection-state')
        logger.info(f"WebRTC 연결 상태: {state}")
        
    def send_offer_to_client(self, offer_data):
        """클라이언트에 Offer 전송"""
        if hasattr(self, 'websocket') and self.websocket:
            asyncio.create_task(self.websocket.send(json.dumps({
                'type': 'offer',
                'data': offer_data
            })))
            
    def send_ice_candidate_to_client(self, candidate_data):
        """클라이언트에 ICE Candidate 전송"""
        if hasattr(self, 'websocket') and self.websocket:
            asyncio.create_task(self.websocket.send(json.dumps({
                'type': 'ice-candidate',
                'data': candidate_data
            })))
            
    async def handle_client(self, websocket, path):
        """클라이언트 연결 처리"""
        self.websocket = websocket
        logger.info(f"클라이언트 연결: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.handle_message(data)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("클라이언트 연결 종료")
        except Exception as e:
            logger.error(f"클라이언트 처리 오류: {e}")
            
    async def handle_message(self, data):
        """클라이언트 메시지 처리"""
        message_type = data.get('type')
        
        if message_type == 'answer':
            await self.handle_answer(data.get('data'))
        elif message_type == 'ice-candidate':
            await self.handle_ice_candidate(data.get('data'))
        elif message_type == 'start':
            await self.start_streaming()
        elif message_type == 'stop':
            await self.stop_streaming()
            
    async def handle_answer(self, answer_data):
        """클라이언트 Answer 처리"""
        sdp_text = answer_data.get('sdp')
        
        # SDP 생성
        sdp = GstSdp.SDPMessage.new()
        sdp.parse_text(sdp_text)
        
        # Answer 설정
        answer = GstWebRTC.WebRTCSessionDescription.new(
            GstWebRTC.WebRTCSDPType.ANSWER, sdp
        )
        
        self.webrtcbin.emit('set-remote-description', answer, None)
        logger.info("Answer 설정 완료")
        
    async def handle_ice_candidate(self, candidate_data):
        """클라이언트 ICE Candidate 처리"""
        candidate = candidate_data.get('candidate')
        mline_index = candidate_data.get('sdpMLineIndex', 0)
        
        # ICE Candidate 추가
        self.webrtcbin.emit('add-ice-candidate', mline_index, candidate)
        logger.info(f"ICE Candidate 추가: {candidate}")
        
    async def start_streaming(self):
        """스트리밍 시작"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
            logger.info("스트리밍 시작")
            
    async def stop_streaming(self):
        """스트리밍 중지"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            logger.info("스트리밍 중지")
            
    def run_gstreamer(self):
        """GStreamer 메인 루프 실행"""
        self.create_pipeline()
        
        # 파이프라인 시작
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
            
        # GStreamer 메인 루프
        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            logger.info("GStreamer 종료")
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
                
    async def start_websocket_server(self):
        """WebSocket 서버 시작"""
        self.websocket_server = await websockets.serve(
            self.handle_client, 
            self.host, 
            self.port
        )
        logger.info(f"WebSocket 서버 시작: {self.host}:{self.port}")
        
    def start(self):
        """서버 시작"""
        # GStreamer 스레드 시작
        gst_thread = threading.Thread(target=self.run_gstreamer, daemon=True)
        gst_thread.start()
        
        # WebSocket 서버 시작
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self.start_websocket_server())
            self.loop.run_forever()
        except KeyboardInterrupt:
            logger.info("서버 종료")
        finally:
            self.loop.close()

if __name__ == '__main__':
    server = WebRTCServer()
    server.start()
