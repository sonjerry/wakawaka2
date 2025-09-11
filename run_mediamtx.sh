#!/bin/bash

# MediaMTX 서버 실행 스크립트

echo "MediaMTX 서버 시작..."

# MediaMTX 설치 확인
if ! command -v mediamtx &> /dev/null; then
    echo "MediaMTX가 설치되지 않았습니다. 먼저 설치하세요."
    exit 1
fi

# MediaMTX 설정 파일 생성
echo "MediaMTX 설정 파일 생성 중..."
cat > mediamtx.yml << 'EOF'
# MediaMTX 설정
rtmp: yes
rtsp: yes
webrtc: yes
hls: no
webrtcEncryption: no
webrtcAllowOrigin: "*"
logLevel: info
logDestinations: [stdout]
api: yes
apiAddress: ":9997"
metrics: yes
metricsAddress: ":9998"
pprof: no
pprofAddress: ":9999"
readTimeout: 10s
writeTimeout: 10s
readBufferCount: 2048
udpMaxPayloadSize: 1472
EOF

echo "MediaMTX 서버 시작 중..."
echo "RTMP 포트: 1935"
echo "WebRTC 포트: 8889"
echo "API 포트: 9997"
echo ""
echo "Ctrl+C로 종료"

# MediaMTX 실행
mediamtx mediamtx.yml
