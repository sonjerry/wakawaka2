#!/bin/bash

# rpicam을 사용한 스트림 시작 스크립트

echo "rpicam 스트림 시작..."

# rpicam 설치 확인
if ! command -v rpicam-vid &> /dev/null; then
    echo "rpicam이 설치되지 않았습니다. 설치 중..."
    sudo apt update
    sudo apt install -y rpicam-apps
fi

# MediaMTX가 실행 중인지 확인
if ! curl -s http://localhost:9997/v3/paths/list > /dev/null; then
    echo "MediaMTX 서버가 실행 중이지 않습니다. 먼저 ./run_mediamtx.sh를 실행하세요."
    exit 1
fi

echo "MediaMTX 서버 연결 확인됨"
echo "rpicam 스트림 시작 중..."

# rpicam으로 H.264 스트림 생성 후 FFmpeg으로 RTMP 전송
rpicam-vid --width 1280 --height 720 --framerate 30 --bitrate 3000000 --codec h264 --output - | ffmpeg -f h264 -i - -c:v copy -f flv rtmp://localhost:1935/live/stream
