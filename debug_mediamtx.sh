#!/bin/bash

# MediaMTX 디버깅 스크립트

echo "=== MediaMTX 디버깅 시작 ==="

# 1. MediaMTX 설치 확인
echo "1. MediaMTX 설치 확인:"
if command -v mediamtx &> /dev/null; then
    echo "✓ MediaMTX가 설치되어 있습니다"
    mediamtx --version
else
    echo "✗ MediaMTX가 설치되지 않았습니다"
    exit 1
fi

# 2. 포트 사용 확인
echo -e "\n2. 포트 사용 확인:"
echo "포트 1935 (RTMP):"
netstat -tlnp | grep :1935 || echo "포트 1935 사용 중이지 않음"

echo "포트 8889 (WebRTC):"
netstat -tlnp | grep :8889 || echo "포트 8889 사용 중이지 않음"

# 3. MediaMTX 프로세스 확인
echo -e "\n3. MediaMTX 프로세스 확인:"
ps aux | grep mediamtx | grep -v grep || echo "MediaMTX 프로세스가 실행 중이지 않음"

# 4. MediaMTX 설정 파일 확인
echo -e "\n4. MediaMTX 설정 파일 확인:"
if [ -f "mediamtx.yml" ]; then
    echo "✓ mediamtx.yml 파일이 존재합니다"
    echo "설정 내용:"
    cat mediamtx.yml
else
    echo "✗ mediamtx.yml 파일이 없습니다"
fi

# 5. 네트워크 연결 테스트
echo -e "\n5. 네트워크 연결 테스트:"
echo "localhost:1935 연결 테스트:"
timeout 3 bash -c "</dev/tcp/localhost/1935" && echo "✓ RTMP 포트 연결 가능" || echo "✗ RTMP 포트 연결 불가"

echo "localhost:8889 연결 테스트:"
timeout 3 bash -c "</dev/tcp/localhost/8889" && echo "✓ WebRTC 포트 연결 가능" || echo "✗ WebRTC 포트 연결 불가"

# 6. MediaMTX 로그 확인
echo -e "\n6. MediaMTX 로그 확인:"
if [ -f "mediamtx.log" ]; then
    echo "최근 로그 (마지막 10줄):"
    tail -10 mediamtx.log
else
    echo "로그 파일이 없습니다"
fi

echo -e "\n=== 디버깅 완료 ==="
