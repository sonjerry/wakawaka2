#!/usr/bin/env bash
set -euo pipefail

# GStreamer WebRTC 스트리밍 스크립트
PORT=8080
WIDTH=640
HEIGHT=480
FPS=15

echo "[gstreamer-webrtc] start: ${WIDTH}x${HEIGHT} @ ${FPS}fps (WebRTC on :${PORT})"
echo "          open your page OR use http://<PI_IP>:${PORT} with WebRTC client"
echo

# GStreamer WebRTC 파이프라인 실행
exec gst-launch-1.0 \
  libcamerasrc \
    ! video/x-raw,width=${WIDTH},height=${HEIGHT},framerate=${FPS}/1 \
    ! videoconvert \
    ! vp8enc deadline=1 keyframe-max-dist=30 \
    ! rtpvp8pay \
    ! webrtcbin name=webrtcbin \
    ! tcpserversink host=0.0.0.0 port=${PORT}
