#!/bin/bash

# MediaMTX 테스트 스크립트

echo "MediaMTX 테스트 시작..."

# MediaMTX 설치 확인
if ! command -v mediamtx &> /dev/null; then
    echo "MediaMTX가 설치되지 않았습니다. 먼저 run_webrtc.sh를 실행하세요."
    exit 1
fi

# MediaMTX 설정 파일 생성
cat > test_mediamtx.yml << 'EOF'
# MediaMTX 테스트 설정
rtmp: yes
rtsp: yes
webrtc: yes
hls: no
webrtcEncryption: no
webrtcAllowOrigin: "*"
logLevel: debug
logDestinations: [stdout]
api: yes
apiAddress: ":9997"
metrics: yes
metricsAddress: ":9998"
readTimeout: 10s
writeTimeout: 10s
readBufferCount: 2048
udpMaxPayloadSize: 1472
EOF

echo "MediaMTX 설정 파일 생성 완료"

# MediaMTX 실행
echo "MediaMTX 서버 시작..."
mediamtx test_mediamtx.yml
