#!/usr/bin/env bash
# 求职 Tracker 一键启动脚本
#
#   bash start.sh
#
# 它会：1) 创建虚拟环境 .venv（已存在则跳过）
#       2) 安装 requirements.txt 里的依赖
#       3) 启动 Flask 应用（默认 http://127.0.0.1:5000）
#
# 可用环境变量：
#   PORT=8080 bash start.sh        # 换端口
#   HOST=127.0.0.1 bash start.sh   # 只监听本机

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
PORT="${PORT:-5000}"
HOST="${HOST:-0.0.0.0}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "错误：找不到 python3，请先安装 Python 3.12。" >&2
  exit 1
fi

echo "==> 使用的 Python：$("$PYTHON" --version 2>&1)"

if [ ! -d ".venv" ]; then
  echo "==> 创建虚拟环境 .venv ..."
  if ! "$PYTHON" -m venv .venv; then
    echo "警告：创建虚拟环境失败（通常是没有安装 python3-venv 软件包）。"
    echo "      改为把依赖安装到当前用户目录后直接启动。"
    echo "      如需虚拟环境，请先执行： sudo apt install -y python3-venv"
    "$PYTHON" -m pip install --user -r requirements.txt \
      || "$PYTHON" -m pip install --user --break-system-packages -r requirements.txt
    echo "==> 启动应用： http://127.0.0.1:${PORT}   （按 Ctrl+C 停止）"
    exec "$PYTHON" main.py
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> 安装依赖 ..."
python -m pip install --upgrade pip >/dev/null 2>&1 || true
python -m pip install -r requirements.txt

echo "==> 启动应用： http://127.0.0.1:${PORT}"
echo "    （按 Ctrl+C 停止）"
exec python main.py
