#!/bin/bash


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

echo "설정 완료. WebRTC 서버를 시작합니다..."
echo "웹 인터페이스: http://100.84.162.124:8000"
echo "WebSocket: ws://100.84.162.124:8080"
echo "비트레이트: 3Mbps (1280x720 @ 30fps)"
echo ""
echo "Ctrl+C로 종료"

# WebRTC 서버 실행
python3 app.py
