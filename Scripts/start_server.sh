#!/bin/bash

# ============================================
# start_server.sh
# Script khởi động server - LOAD MODEL TỪ LOCAL
# ============================================

set -e  # Exit on error

echo "============================================"
echo " Multi-Agent LLM API Server Startup"
echo "============================================"
echo ""

# ============================================
# CHECK PREREQUISITES
# ============================================

echo " Kiểm tra điều kiện tiên quyết..."

# Check Python
if ! command -v python &> /dev/null; then
    echo " Python không tìm thấy. Vui lòng cài Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo " Python $PYTHON_VERSION"

# Check CUDA
if ! command -v nvidia-smi &> /dev/null; then
    echo "  nvidia-smi không tìm thấy. GPU có thể không khả dụng."
else
    echo " NVIDIA GPU:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader | head -1
fi

# Check virtual environment
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo "  Không trong virtual environment"
    echo "   Đang kích hoạt venv..."
    
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo " Đã kích hoạt venv"
    else
        echo " Không tìm thấy venv. Chạy ./setup.sh trước"
        exit 1
    fi
else
    echo " Virtual environment: $VIRTUAL_ENV"
fi

echo ""

# ============================================
# LOAD ENVIRONMENT VARIABLES
# ============================================

echo "  Đang load environment variables..."

if [ -f .env ]; then
    echo " Tìm thấy .env file"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo " Không tìm thấy .env file"
    echo "   Chạy ./setup.sh hoặc copy .env.example thành .env"
    exit 1
fi

echo ""

# ============================================
# VALIDATE CONFIGURATION
# ============================================

echo " Kiểm tra cấu hình..."

# Check MODEL_PATH
if [ -z "$MODEL_PATH" ]; then
    echo " MODEL_PATH chưa được set trong .env"
    exit 1
fi

echo "   Model: $MODEL_PATH"

# Kiểm tra model có tồn tại không
if [ ! -d "$MODEL_PATH" ]; then
    echo " Model không tồn tại tại: $MODEL_PATH"
    echo "   Vui lòng kiểm tra lại đường dẫn trong .env"
    exit 1
else
    echo " Tìm thấy model tại: $MODEL_PATH"
    
    # Kiểm tra các file cần thiết của model
    if [ ! -f "$MODEL_PATH/config.json" ]; then
        echo "  Cảnh báo: Không tìm thấy config.json trong model folder"
    fi
fi

echo "   Port: ${PORT:-8000}"
echo "   GPU Memory: ${GPU_MEMORY_UTILIZATION:-0.80}"
echo "   Max Seqs: ${MAX_NUM_SEQS:-4}"

echo ""

# ============================================
# CHECK DEPENDENCIES
# ============================================

echo " Kiểm tra dependencies..."

if ! python -c "import vllm" &> /dev/null; then
    echo " vLLM chưa được cài"
    echo "   Chạy: pip install -r requirements.txt"
    exit 1
fi

if ! python -c "import fastapi" &> /dev/null; then
    echo " FastAPI chưa được cài"
    echo "   Chạy: pip install -r requirements.txt"
    exit 1
fi

echo " Tất cả dependencies đã sẵn sàng"
echo ""

# ============================================
# CHECK DATA FOLDERS
# ============================================

echo " Kiểm tra thư mục dữ liệu..."

# Check documents folder
if [ ! -d "./documents" ]; then
    echo "  Thư mục ./documents/ không tồn tại"
    mkdir -p ./documents
    echo "   Đã tạo ./documents/"
else
    DOC_COUNT=$(find ./documents -type f | wc -l)
    echo " ./documents/ ($DOC_COUNT files)"
    
    if [ $DOC_COUNT -eq 0 ]; then
        echo "     Chưa có tài liệu nào. Vui lòng thêm file vào ./documents/"
    fi
fi

# Check data folder
if [ ! -d "./data" ]; then
    echo "  Thư mục ./data/ không tồn tại"
    mkdir -p ./data
    echo "   Đã tạo ./data/"
else
    echo " ./data/"
    
    if [ -f "./data/orders.csv" ]; then
        ORDER_COUNT=$(wc -l < ./data/orders.csv)
        echo "   - orders.csv ($ORDER_COUNT dòng)"
    else
        echo "   Chưa có orders.csv"
    fi
    
    if [ -f "./data/customer_profiles.json" ]; then
        echo "   - customer_profiles.json"
    fi
fi

echo ""

# ============================================
# START SERVER
# ============================================

echo "============================================"
echo "Đang khởi động FastAPI Server..."
echo "============================================"
echo ""
echo "   URL: http://${HOST:-0.0.0.0}:${PORT:-8000}"
echo "   Docs: http://localhost:${PORT:-8000}/docs"
echo "   Model: $MODEL_PATH"
echo ""
echo "Đang load model... (có thể mất 1-2 phút)"
echo "   Nhấn Ctrl+C để dừng server"
echo ""
echo "============================================"
echo ""

# Start server
python api_server.py

# ============================================
# CLEANUP (if script is interrupted)
# ============================================

echo ""
echo "============================================"
echo "Server đã dừng"
echo "============================================"