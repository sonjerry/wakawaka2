#!/bin/bash

# 라즈베리파이용 가상환경 설정 스크립트

echo "Python 가상환경 설정 중..."

# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# pip 업그레이드
pip install --upgrade pip

# 의존성 설치 (최소 버전)
pip install -r requirements_minimal.txt

# sdp-transform 설치 시도 (선택사항)
pip install sdp-transform || echo "sdp-transform 설치 실패 - 기본 기능으로 계속 진행"

echo "가상환경 설정 완료!"
echo ""
echo "가상환경 활성화 방법:"
echo "source venv/bin/activate"
echo ""
echo "가상환경 비활성화 방법:"
echo "deactivate"
echo ""
echo "서버 실행 방법:"
echo "source venv/bin/activate"
echo "python app.py"
