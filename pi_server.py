#!/usr/bin/env python3
import subprocess
import threading
import time
import os
from flask import Flask, render_template_string, Response
import cv2
import numpy as np

app = Flask(__name__)

# HTML 템플릿 (인라인)
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
        
        function connect() {
            video.src = '/video_feed';
            video.load();
            
            video.onloadstart = () => status.textContent = '연결 중...';
            video.oncanplay = () => status.textContent = '연결됨';
            video.onerror = () => {
                status.textContent = '연결 실패';
                setTimeout(connect, 1000);
            };
        }
        
        connect();
    </script>
</body>
</html>
'''

def get_camera_stream():
    """OpenCV로 카메라 스트림 생성 (최소 지연시간)"""
    cap = cv2.VideoCapture(0)  # libcamera 사용
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 버퍼 크기 최소화
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # JPEG 압축 (최소 지연)
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/video_feed')
def video_feed():
    return Response(get_camera_stream(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("RC카 서버 시작...")
    print("브라우저에서 http://localhost:8080 접속")
    app.run(host='0.0.0.0', port=8080, threaded=True)
