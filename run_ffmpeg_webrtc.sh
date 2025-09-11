#!/usr/bin/env bash
set -euo pipefail

# FFmpeg + WebRTC 스트리밍
PORT=8080
WIDTH=640
HEIGHT=480
FPS=15

echo "[ffmpeg-webrtc] start: ${WIDTH}x${HEIGHT} @ ${FPS}fps (WebRTC on :${PORT})"
echo "          open your page OR use http://<PI_IP>:${PORT} with WebRTC client"
echo

# FFmpeg로 WebRTC 스트림 생성
exec ffmpeg \
  -f libcamera \
  -video_size ${WIDTH}x${HEIGHT} \
  -framerate ${FPS} \
  -i 0 \
  -c:v libvpx \
  -b:v 1M \
  -f rtp \
  rtp://0.0.0.0:${PORT}
