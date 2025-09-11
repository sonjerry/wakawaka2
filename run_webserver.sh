#!/bin/bash

# 웹서버 실행 스크립트 (가상환경 사용)

echo "웹서버 시작..."

# 가상환경 확인
if [ ! -d "venv" ]; then
    echo "가상환경이 없습니다. 먼저 가상환경을 생성하세요."
    echo "python3 -m venv venv"
    exit 1
fi

# 가상환경 활성화
echo "가상환경 활성화 중..."
source venv/bin/activate

# Python 의존성 설치
echo "Python 의존성 설치 중..."
pip install -r requirements.txt

# 웹서버 실행
echo "Flask 웹서버 시작 중..."
echo "웹 인터페이스: http://100.84.162.124:8000"
echo "API 엔드포인트: http://100.84.162.124:8000/api/"
echo ""
echo "Ctrl+C로 종료"

# Flask 서버 실행
python app.py
