#!/bin/bash

# 전체 설정 및 실행 스크립트

echo "=== RC카 프로젝트 설정 시작 ==="

# 실행 권한 자동 부여
echo "실행 권한 부여 중..."
chmod +x *.sh

# Git 강제 덮어쓰기 (로컬 변경사항 무시)
echo "Git 강제 업데이트 중..."
git fetch origin
git reset --hard origin/master

# 가상환경 생성
echo "가상환경 생성 중..."
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
echo "Python 의존성 설치 중..."
pip install -r requirements.txt

echo "=== 설정 완료 ==="
echo ""
echo "사용 방법:"
echo "1. MediaMTX 서버: ./run_mediamtx.sh"
echo "2. 웹서버: ./run_webserver.sh"
echo "3. 스트림 시작: ./start_rpicam_stream.sh"
echo ""
echo "또는 통합 실행:"
echo "./run_mediamtx.sh &"
echo "./run_webserver.sh &"
echo "./start_rpicam_stream.sh"
