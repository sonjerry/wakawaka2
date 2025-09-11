#!/usr/bin/env bash
set -euo pipefail

# 최소 지연시간 스트리밍
PORT=8080
WIDTH=640
HEIGHT=480
FPS=30

echo "[low-latency-stream] start: ${WIDTH}x${HEIGHT} @ ${FPS}fps (HTTP on :${PORT})"
echo "          open your page OR use http://<PI_IP>:${PORT} with client"
echo

# 최소 지연시간으로 libcamera-vid 실행
exec libcamera-vid \
  --width=${WIDTH} \
  --height=${HEIGHT} \
  --framerate=${FPS} \
  --bitrate=2000000 \
  --inline \
  --listen \
  --timeout=0 \
  -o tcp://0.0.0.0:${PORT}
