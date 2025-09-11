#!/bin/bash

# 웹서버 실행 스크립트
# 라즈베리파이에서 실행

echo "웹서버 시작..."

# Python 의존성 설치
pip3 install -r requirements.txt

echo "웹서버를 시작합니다..."
echo "웹 인터페이스: http://100.84.162.124:8000"
echo "WebSocket: ws://100.84.162.124:8080"
echo ""
echo "Ctrl+C로 종료"

# 웹서버 실행
python3 app.py
