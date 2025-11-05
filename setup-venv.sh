#!/bin/bash
# ============================================
# setup_venv.sh — macOS용 Python 가상환경 관리 스크립트
# (pyenv 확인 + 자동 설치 안내 + 기존 venv 검증 + requirements 업데이트)
# ============================================

set -e
trap 'echo "❌ 오류 발생: 스크립트를 종료합니다."; exit 1' ERR

echo "--------------------------------------------"
echo "🔍 Python 가상환경 자동 설정 시작"
echo "--------------------------------------------"

# 1️⃣ pyenv 존재 여부 확인
if ! command -v pyenv &> /dev/null; then
    echo "❌ pyenv가 설치되어 있지 않습니다."
    echo ""
    echo "📦 설치 방법:"
    echo "  brew update && brew install pyenv"
    echo ""
    echo "설치 후 다음 명령으로 초기화하세요:"
    echo '  echo -e "\n# pyenv init\nexport PYENV_ROOT=\"$HOME/.pyenv\"\ncommand -v pyenv >/dev/null && eval \"$(pyenv init -)\"" >> ~/.zshrc'
    echo "  exec \$SHELL"
    exit 1
fi

echo "⚙️ pyenv 환경 감지됨: $(which pyenv)"

# 2️⃣ .python-version 확인
if [ -f ".python-version" ]; then
    PY_VERSION=$(cat .python-version | tr -d '[:space:]')
    echo "📘 .python-version 감지됨: $PY_VERSION"
else
    PY_VERSION="3.11.9"
    echo "⚠️ .python-version 없음 → 기본 버전 $PY_VERSION 사용"
fi

# 3️⃣ pyenv 초기화 및 버전 준비
export PYENV_ROOT="$HOME/.pyenv"
if command -v brew &> /dev/null; then
    BREW_PREFIX=$(brew --prefix)
    export PATH="$BREW_PREFIX/bin:$PATH"
fi
eval "$(pyenv init -)" >/dev/null 2>&1

if ! pyenv versions --bare | grep -qx "$PY_VERSION"; then
    echo "📦 pyenv에 Python $PY_VERSION 버전이 없습니다. 설치 중..."
    pyenv install "$PY_VERSION"
else
    echo "✅ pyenv에 Python $PY_VERSION 이미 설치됨"
fi

pyenv local "$PY_VERSION"
eval "$(pyenv init -)" >/dev/null 2>&1
PY_CMD="$(pyenv which python)"

# 4️⃣ 가상환경 디렉토리 확인
VENV_DIR=".venv"

if [ -d "$VENV_DIR" ]; then
    echo "🧩 기존 가상환경($VENV_DIR) 감지됨"

    # 4-1️⃣ 가상환경 활성화 여부 확인
    if [[ -z "$VIRTUAL_ENV" ]]; then
        echo "⚠️ 가상환경이 활성화되어 있지 않습니다."
        echo "다음 명령으로 활성화 후 다시 실행하세요:"
        echo "  source .venv/bin/activate"
        exit 1
    fi

    # 4-2️⃣ Python 버전 일치 확인
    ACTIVE_VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
    if [ "$ACTIVE_VER" != "$PY_VERSION" ]; then
        echo "❌ 현재 활성화된 Python 버전($ACTIVE_VER)이 .python-version($PY_VERSION)과 다릅니다."
        echo "  → pyenv local $PY_VERSION && source .venv/bin/activate 후 다시 실행하세요."
        exit 1
    fi

    # 4-3️⃣ requirements 업데이트
    if [ -f "requirements.txt" ]; then
        echo "📦 requirements.txt 변경사항 적용 중 (업데이트 모드)"
        pip install --upgrade pip
        pip install --upgrade -r requirements.txt
        echo "✅ 라이브러리 버전 업데이트 완료"
    else
        echo "⚠️ requirements.txt 없음 → 업데이트 건너뜀"
    fi

    echo ""
    echo "--------------------------------------------"
    echo "🎉 가상환경 유지 + requirements 업데이트 완료!"
    echo "Python 경로: $(which python)"
    python --version
    echo "pip 버전: $(pip --version)"
    echo "--------------------------------------------"
    exit 0
fi

# 5️⃣ 가상환경 새로 생성
echo "🐍 $PY_VERSION 기반 새 가상환경 생성 중..."
"$PY_CMD" -m venv "$VENV_DIR"

# 6️⃣ 가상환경 활성화
source "$VENV_DIR/bin/activate"
echo "✅ 가상환경 활성화 완료"

# 7️⃣ pip 업그레이드 및 requirements 설치
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "📦 requirements.txt 설치 중..."
    pip install -r requirements.txt
else
    echo "⚠️ requirements.txt 없음 → 설치 건너뜀"
fi

# 8️⃣ 최종 확인
echo ""
echo "--------------------------------------------"
echo "🎉 새로운 가상환경 생성 및 초기화 완료!"
echo "Python 경로: $(which python)"
python --version
echo "pip 버전: $(pip --version)"
echo "--------------------------------------------"
