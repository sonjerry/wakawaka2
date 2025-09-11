#!/bin/bash

# GStreamer WebRTC 서버 실행 스크립트
# 라즈베리파이에서 실행

echo "GStreamer WebRTC 서버 시작..."

# 필요한 패키지 설치 확인
echo "필요한 패키지 확인 중..."

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

echo "설정 완료. 서버를 시작합니다..."

# WebRTC 서버 실행
python3 webrtc_server.py
