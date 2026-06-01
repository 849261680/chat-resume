#!/bin/bash

# Chat Resume 后端重启脚本
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_LOG_FILE="${BACKEND_LOG_FILE:-logs/backend.log}"

# 本地默认保留结构化日志和 Agent trace。
export LOG_FORMAT="${LOG_FORMAT:-text}"
export BACKEND_LOG_FILE
export AGENT_TRACE_LOG_ENABLED="${AGENT_TRACE_LOG_ENABLED:-true}"

echo "🚀 重启 Chat Resume 后端服务..."

# 检查是否在正确的目录
if [ ! -f "backend/pyproject.toml" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 进入后端目录
cd backend

# 检查是否存在 .env 文件
if [ ! -f ".env" ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请根据需要修改配置"
fi

# 检查 Python 环境
if ! command -v uv &> /dev/null; then
    echo "❌ 错误: 未找到 uv，请先安装 uv"
    exit 1
fi

configure_macos_proxy() {
    # 用于让本地后端继承 macOS 系统 HTTPS 代理，修复 Google OAuth 直连超时。
    if [ -n "${HTTPS_PROXY:-}" ] || [ "$(uname -s)" != "Darwin" ]; then
        return
    fi

    if ! command -v networksetup &> /dev/null; then
        return
    fi

    local service="${MACOS_PROXY_SERVICE:-Wi-Fi}"
    local proxy_info
    proxy_info="$(networksetup -getsecurewebproxy "${service}" 2>/dev/null || true)"
    if ! printf '%s\n' "${proxy_info}" | grep -q '^Enabled: Yes'; then
        return
    fi

    local host
    local port
    host="$(printf '%s\n' "${proxy_info}" | awk '/^Server: / {print $2}')"
    port="$(printf '%s\n' "${proxy_info}" | awk '/^Port: / {print $2}')"
    if [ -z "${host}" ] || [ -z "${port}" ]; then
        return
    fi

    export HTTP_PROXY="${HTTP_PROXY:-http://${host}:${port}}"
    export HTTPS_PROXY="${HTTPS_PROXY:-http://${host}:${port}}"
    export ALL_PROXY="${ALL_PROXY:-http://${host}:${port}}"
    export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,*.local}"
    echo "🌐 已启用本地代理: ${HTTPS_PROXY}"
}

stop_port() {
    local port="$1"
    local pids
    pids="$(
        { lsof -nP -ti "tcp:${port}" 2>/dev/null || true; } \
            | while read -r pid; do
                [ -n "${pid}" ] || continue
                command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
                if printf '%s\n' "${command_line}" \
                    | grep -Eq 'backend\.sh|uvicorn app\.main:app|chat-resume/backend'; then
                    echo "${pid}"
                fi
            done
    )"
    if [ -n "${pids}" ]; then
        echo "🛑 停止占用端口 ${port} 的进程: ${pids}"
        kill ${pids} || true
        sleep 1
        pids="$(
            echo "${pids}" \
                | while read -r pid; do
                    [ -n "${pid}" ] || continue
                    if kill -0 "${pid}" 2>/dev/null; then
                        echo "${pid}"
                    fi
                done
        )"
        if [ -n "${pids}" ]; then
            echo "🛑 强制停止占用端口 ${port} 的进程: ${pids}"
            kill -9 ${pids} || true
        fi
    fi
}

configure_macos_proxy

# 创建并同步虚拟环境
echo "📦 使用 uv 同步依赖..."
uv sync --extra dev

# 检查数据库
echo "🗄️ 初始化数据库..."
if [ ! -f "chat_resume.db" ]; then
    echo "创建数据库文件..."
fi

# 创建上传目录
mkdir -p uploads logs
touch "${BACKEND_LOG_FILE}"

# 重启服务
stop_port "${BACKEND_PORT}"

echo "🌟 启动后端服务..."
echo "后端将在 http://localhost:${BACKEND_PORT} 运行"
echo "API 文档: http://localhost:${BACKEND_PORT}/docs"
echo "日志文件: backend/${BACKEND_LOG_FILE}"
echo "日志格式: ${LOG_FORMAT}; Agent trace: ${AGENT_TRACE_LOG_ENABLED}"
echo "终端彩色输出；日志文件保持无色纯文本。"
echo "按 Ctrl+C 停止服务"
echo ""

uv run uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT}" --reload --reload-dir app
