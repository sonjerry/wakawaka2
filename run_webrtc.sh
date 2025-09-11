#!/bin/bash

# FFmpeg 및 MediaMTX 설치
echo "필요한 패키지 설치 중..."
sudo apt update
sudo apt install -y ffmpeg

# MediaMTX 다운로드 및 설치
echo "MediaMTX 설치 중..."
wget https://github.com/bluenviron/mediamtx/releases/download/v1.14.0/mediamtx_v1.14.0_linux_arm64v8.tar.gz
tar -xzf mediamtx_v1.14.0_linux_arm64v8.tar.gz
sudo mv mediamtx /usr/local/bin/
sudo chmod +x /usr/local/bin/mediamtx
rm mediamtx_v1.14.0_linux_arm64v8.tar.gz

# Python 의존성 설치
echo "Python 의존성 설치 중..."
pip3 install -r requirements.txt

# 카메라 권한 설정
sudo usermod -a -G video $USER
sudo usermod -a -G render $USER

# GPU 메모리 할당 증가
echo "GPU 메모리 설정 중..."
sudo raspi-config nonint do_memory_split 128

# 카메라 활성화
echo "카메라 활성화 중..."
sudo raspi-config nonint do_camera 0

# 네트워크 최적화 (3Mbps 스트리밍용)
echo "네트워크 최적화 중..."
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.ipv4.udp_rmem_min=8192
sudo sysctl -w net.ipv4.udp_wmem_min=8192

# CPU 성능 모드 설정
echo "CPU 성능 모드 설정 중..."
echo 'performance' | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

echo "설정 완료. FFmpeg + MediaMTX 서버를 시작합니다..."
echo "웹 인터페이스: http://100.84.162.124:8000"
echo "MediaMTX WebRTC: http://100.84.162.124:8889"
echo "RTMP 스트림: rtmp://100.84.162.124:1935/live/stream"
echo "비트레이트: 3Mbps (1280x720 @ 30fps)"
echo ""
echo "Ctrl+C로 종료"

# MediaMTX 서버 백그라운드 실행
echo "MediaMTX 서버 시작 중..."
mediamtx &
MEDIAMTX_PID=$!

# Flask 서버 실행
echo "Flask 서버 시작 중..."
python3 app.py &
FLASK_PID=$!

# 프로세스 종료 처리
cleanup() {
    echo "서버 종료 중..."
    kill $MEDIAMTX_PID 2>/dev/null
    kill $FLASK_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# 프로세스 대기
wait
