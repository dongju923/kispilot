"""KIS 접속 설정 — 도메인, 데이터 폴더, 앱키·계좌.

앱키·계좌는 환경변수 → OS 키체인 순으로 찾는다 (kispilot/credentials.py).
처음 쓰는 사용자는 `kispilot setup` 으로 키체인에 저장한다.
개발할 때는 현재 폴더의 .env 도 환경변수로 읽는다 (.env 는 .gitignore 대상).
"""
import os

from dotenv import find_dotenv, load_dotenv

from kispilot import credentials
from kispilot.paths import data_dir

load_dotenv(find_dotenv(usecwd=True))

DOMAIN = {"real": "https://openapi.koreainvestment.com:9443", "paper": "https://openapivts.koreainvestment.com:29443"}
WS_DOMAIN = {"real": "ws://ops.koreainvestment.com:21000", "paper": "ws://ops.koreainvestment.com:31000"}

# 토큰 캐시 · 종목 마스터 · 커스텀 전략 (사용자 데이터 폴더)
BASE_CACHE_PATH = str(data_dir())

REAL_APPKEY = credentials.get("REAL_APPKEY")
REAL_APP_SECRET = credentials.get("REAL_APP_SECRET")
PAPER_APPKEY = credentials.get("PAPER_APPKEY")
PAPER_APP_SECRET = credentials.get("PAPER_APP_SECRET")
CANO = credentials.get("CANO")
ACNT_PRDT_CD = credentials.get("ACNT_PRDT_CD")
PAPER_CANO = credentials.get("PAPER_CANO")
PAPER_ACNT_PRDT_CD = credentials.get("PAPER_ACNT_PRDT_CD")
