#!/bin/bash

# FFmpeg 스트림 시작 스크립트

echo "FFmpeg 스트림 시작..."

# 카메라 장치 확인
if [ ! -e "/dev/video0" ]; then
    echo "카메라 장치를 찾을 수 없습니다. /dev/video0이 존재하지 않습니다."
    echo "사용 가능한 비디오 장치:"
    ls -la /dev/video* 2>/dev/null || echo "비디오 장치가 없습니다"
    exit 1
fi

# MediaMTX가 실행 중인지 확인
if ! curl -s http://localhost:9997/v3/paths/list > /dev/null; then
    echo "MediaMTX 서버가 실행 중이지 않습니다. 먼저 ./run_mediamtx.sh를 실행하세요."
    exit 1
fi

echo "카메라 장치 확인됨: /dev/video0"
echo "MediaMTX 서버 연결 확인됨"
echo "FFmpeg 스트림 시작 중..."

# FFmpeg 명령어 실행
ffmpeg -f v4l2 -input_format h264 -video_size 1280x720 -framerate 30 -i /dev/video0 -c:v copy -f flv rtmp://localhost:1935/live/stream
