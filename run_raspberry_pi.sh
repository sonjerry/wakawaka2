#!/bin/bash

# 라즈베리파이용 통합 서버 실행 스크립트
# 3Mbps 최적화 설정

echo "라즈베리파이 RC카 서버 시작..."

# 시스템 업데이트 및 필요한 패키지 설치
echo "필요한 패키지 설치 중..."

# GStreamer 및 WebRTC 플러그인 설치
sudo apt update
sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav
sudo apt install -y gstreamer1.0-plugins-rs gstreamer1.0-rtsp gstreamer1.0-x gstreamer1.0-alsa gstreamer1.0-gl gstreamer1.0-gtk3 gstreamer1.0-qt5 gstreamer1.0-pulseaudio
sudo apt install -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0
sudo apt install -y libcamera-tools

# Python 의존성 설치
pip3 install -r requirements.txt

# 카메라 권한 설정
sudo usermod -a -G video $USER
sudo usermod -a -G render $USER

# GPU 메모리 할당 증가 (카메라 성능 향상)
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

# 서버 실행
echo "서버 시작 중..."
echo "웹 인터페이스: http://100.84.162.124:8000"
echo "WebSocket: ws://100.84.162.124:8080"
echo "비트레이트: 3Mbps (1280x720 @ 30fps)"
echo ""
echo "Ctrl+C로 종료"

python3 app.py
