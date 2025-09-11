#!/usr/bin/env bash
set -euo pipefail

# RC카용 최소 지연시간 서버
echo "RC카 서버 시작..."

# 1. libcamera-vid로 최소 지연시간 스트림 생성
libcamera-vid \
  --width=640 \
  --height=480 \
  --framerate=30 \
  --bitrate=2000000 \
  --inline \
  --listen \
  --timeout=0 \
  -o tcp://0.0.0.0:8080 &

# 2. Python HTTP 서버로 웹페이지 서빙
python3 -m http.server 8081 --bind 0.0.0.0 &

# 3. 간단한 프록시 서버 (CORS 해결)
python3 -c "
import http.server
import socketserver
from urllib.request import urlopen
import json

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = '''<!doctype html>
<html><head><meta charset=utf-8><title>RC카 뷰어</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#000;font-family:Arial}
video{width:100vw;height:100vh;object-fit:cover}
.status{position:fixed;top:10px;left:10px;color:white;background:rgba(0,0,0,0.7);padding:5px 10px;border-radius:3px}
</style></head><body>
<div class=status id=status>연결 중...</div>
<video id=video playsinline muted autoplay></video>
<script>
const video=document.getElementById('video');
const status=document.getElementById('status');
function connect(){
  video.src='http://localhost:8080';
  video.load();
  video.onloadstart=()=>status.textContent='연결 중...';
  video.oncanplay=()=>status.textContent='연결됨';
  video.onerror=()=>{status.textContent='연결 실패';setTimeout(connect,1000)};
}
connect();
</script></body></html>'''
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

with socketserver.TCPServer(('0.0.0.0', 8082), ProxyHandler) as httpd:
    print('RC카 뷰어: http://localhost:8082')
    httpd.serve_forever()
" &

echo "RC카 서버 실행 완료!"
echo "브라우저에서 http://localhost:8082 접속"
echo "또는 http://<PI_IP>:8082 접속"

# 모든 프로세스 유지
wait
