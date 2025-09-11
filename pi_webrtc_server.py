#!/usr/bin/env python3
import subprocess
import threading
import time
import json
import asyncio
import websockets
from flask import Flask, render_template_string
import os

app = Flask(__name__)

# HTML 템플릿 (WebRTC)
HTML_TEMPLATE = '''
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RC카 뷰어</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #000; font-family: Arial, sans-serif; }
        video { width: 100vw; height: 100vh; object-fit: cover; }
        .status { position: fixed; top: 10px; left: 10px; color: white; background: rgba(0,0,0,0.7); padding: 5px 10px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="status" id="status">연결 중...</div>
    <video id="video" playsinline muted autoplay></video>
    <script>
        const video = document.getElementById('video');
        const status = document.getElementById('status');
        let pc = null;
        let ws = null;

        async function connect() {
            try {
                // WebSocket 연결
                ws = new WebSocket('ws://localhost:8081');
                
                ws.onopen = () => {
                    status.textContent = 'WebSocket 연결됨';
                    startWebRTC();
                };
                
                ws.onmessage = async (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === 'offer') {
                        await handleOffer(data.sdp);
                    }
                };
                
                ws.onclose = () => {
                    status.textContent = '연결 끊김';
                    setTimeout(connect, 1000);
                };
                
            } catch (err) {
                status.textContent = `오류: ${err.message}`;
                setTimeout(connect, 2000);
            }
        }

        async function startWebRTC() {
            pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });
            
            pc.ontrack = (event) => {
                video.srcObject = event.streams[0];
                status.textContent = 'WebRTC 연결됨';
            };
            
            pc.onicecandidate = (event) => {
                if (event.candidate) {
                    ws.send(JSON.stringify({
                        type: 'ice-candidate',
                        candidate: event.candidate
                    }));
                }
            };
        }

        async function handleOffer(sdp) {
            await pc.setRemoteDescription({ type: 'offer', sdp });
            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);
            
            ws.send(JSON.stringify({
                type: 'answer',
                sdp: answer.sdp
            }));
        }

        connect();
    </script>
</body>
</html>
'''

def start_gstreamer():
    """GStreamer WebRTC 파이프라인 시작"""
    cmd = [
        'gst-launch-1.0',
        'libcamerasrc',
        '!', 'video/x-raw,width=640,height=480,framerate=30/1',
        '!', 'videoconvert',
        '!', 'vp8enc', 'deadline=1', 'keyframe-max-dist=30',
        '!', 'rtpvp8pay',
        '!', 'webrtcbin', 'name=webrtcbin',
        '!', 'tcpserversink', 'host=0.0.0.0', 'port=8081'
    ]
    
    subprocess.run(cmd)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("RC카 WebRTC 서버 시작...")
    print("브라우저에서 http://localhost:8080 접속")
    
    # GStreamer 백그라운드 실행
    gst_thread = threading.Thread(target=start_gstreamer)
    gst_thread.daemon = True
    gst_thread.start()
    
    # Flask 서버 실행
    app.run(host='0.0.0.0', port=8080, threaded=True)
