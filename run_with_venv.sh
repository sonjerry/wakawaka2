#!/bin/bash

# 가상환경에서 서버 실행 스크립트

echo "가상환경에서 RC카 서버 시작..."

# 가상환경 활성화
source venv/bin/activate

# 서버 실행
python app.py
