#!/bin/bash

# 라즈베리파이용 가상환경 설정 스크립트

echo "Python 가상환경 설정 중..."

# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# pip 업그레이드
pip install --upgrade pip

# 의존성 설치
pip install -r requirements.txt

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
