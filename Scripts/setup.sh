#!/bin/bash

# ============================================
# setup.sh
# Script cài đặt ban đầu - LOAD MODEL TỪ LOCAL
# ============================================

set -e  # Exit on error

echo "============================================"
echo " Multi-Agent LLM API Setup"
echo "============================================"
echo ""

# ============================================
# 1. CHECK PREREQUISITES
# ============================================

echo " Bước 1: Kiểm tra điều kiện tiên quyết..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo " Python 3 không tìm thấy. Vui lòng cài Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo " Python $PYTHON_VERSION đã cài"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo " pip3 không tìm thấy. Đang cài..."
    sudo apt update
    sudo apt install -y python3-pip
fi

echo " pip3 đã cài"

# Check git
if ! command -v git &> /dev/null; then
    echo "  git không tìm thấy. Đang cài..."
    sudo apt install -y git
fi

echo " git đã cài"

# Check CUDA (optional)
if command -v nvidia-smi &> /dev/null; then
    echo " NVIDIA GPU được phát hiện:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1
else
    echo "  nvidia-smi không tìm thấy. GPU có thể không khả dụng."
    echo "   Nếu bạn có NVIDIA GPU, hãy cài CUDA toolkit và drivers."
fi

echo ""

# ============================================
# 2. CREATE VIRTUAL ENVIRONMENT
# ============================================

echo " Bước 2: Thiết lập virtual environment..."
echo ""

if [ -d "venv" ]; then
    echo "  Virtual environment đã tồn tại."
    read -p "   Xóa và tạo lại? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        echo "   Đã xóa venv cũ"
    else
        echo "   Giữ venv hiện tại"
    fi
fi

if [ ! -d "venv" ]; then
    echo "   Đang tạo virtual environment..."
    python3 -m venv venv
    echo " Virtual environment đã được tạo"
fi

# Activate venv
source venv/bin/activate
echo " Virtual environment đã kích hoạt"

echo ""

# ============================================
# 3. UPGRADE PIP
# ============================================

echo "  Bước 3: Nâng cấp pip..."
echo ""

pip install --upgrade pip setuptools wheel
echo " pip đã được nâng cấp"

echo ""

# ============================================
# 4. INSTALL DEPENDENCIES
# ============================================

echo " Bước 4: Cài đặt dependencies..."
echo ""

# Check if PyTorch is already installed
if python -c "import torch" &> /dev/null; then
    TORCH_VERSION=$(python -c "import torch; print(torch.__version__)")
    echo " PyTorch $TORCH_VERSION đã cài"
    
    # Check CUDA
    CUDA_AVAILABLE=$(python -c "import torch; print(torch.cuda.is_available())")
    if [ "$CUDA_AVAILABLE" = "True" ]; then
        CUDA_VERSION=$(python -c "import torch; print(torch.version.cuda)")
        echo " CUDA $CUDA_VERSION khả dụng trong PyTorch"
    else
        echo "  CUDA không khả dụng trong PyTorch"
    fi
else
    echo "   Đang cài PyTorch với CUDA 12.1..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    echo " PyTorch đã cài"
fi

echo ""
echo "   Đang cài các dependencies khác..."
pip install -r requirements.txt
echo " Tất cả dependencies đã cài"

echo ""

# ============================================
# 5. CREATE CONFIGURATION
# ============================================

echo "  Bước 5: Tạo file cấu hình..."
echo ""

if [ -f ".env" ]; then
    echo "  File .env đã tồn tại"
    read -p "   Ghi đè? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp .env.example .env
        echo " .env đã được tạo từ template"
    else
        echo "   Giữ .env hiện tại"
    fi
else
    cp .env.example .env
    echo " .env đã được tạo từ template"
fi

echo ""

# ============================================
# 6. CONFIGURE MODEL PATH
# ============================================

echo " Bước 6: Cấu hình đường dẫn model..."
echo ""

read -p "Nhập đường dẫn đến model đã finetune trên máy: " MODEL_PATH

if [ -z "$MODEL_PATH" ]; then
    echo "  Không nhập đường dẫn. Sử dụng mặc định."
    MODEL_PATH="/path/to/your/model"
else
    # Kiểm tra đường dẫn có tồn tại không
    if [ -d "$MODEL_PATH" ]; then
        echo " Tìm thấy model tại: $MODEL_PATH"
        
        # Cập nhật vào .env
        sed -i "s|MODEL_PATH=.*|MODEL_PATH=$MODEL_PATH|" .env
        echo " Đã cập nhật MODEL_PATH trong .env"
    else
        echo " Đường dẫn không tồn tại: $MODEL_PATH"
        echo "   Vui lòng chỉnh sửa .env sau khi setup"
    fi
fi

echo ""

# ============================================
# 7. CREATE DIRECTORIES
# ============================================

echo " Bước 7: Tạo các thư mục cần thiết..."
echo ""

mkdir -p documents
mkdir -p data
mkdir -p logs

echo " Đã tạo thư mục:"
echo "   - ./documents/  (chứa tài liệu sản phẩm)"
echo "   - ./data/       (chứa customer profiles, orders)"
echo "   - ./logs/       (chứa log files)"

echo ""

# ============================================
# 8. MAKE SCRIPTS EXECUTABLE
# ============================================

echo " Bước 8: Cấp quyền thực thi cho scripts..."
echo ""

chmod +x start_server.sh
chmod +x setup.sh
echo " Scripts đã có quyền thực thi"

echo ""

# ============================================
# 9. CREATE SAMPLE DATA
# ============================================

echo " Bước 9: Tạo dữ liệu mẫu..."
echo ""

read -p "Tạo file tài liệu mẫu trong ./documents/? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    python document_handler.py
    echo " Đã tạo file tài liệu mẫu"
else
    echo "   Bỏ qua. Bạn cần tự thêm file vào ./documents/"
fi

echo ""

read -p "Tạo file đơn hàng mẫu trong ./data/? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    python check_order_handler.py
    echo " Đã tạo file đơn hàng mẫu"
else
    echo "   Bỏ qua. Bạn cần tự thêm file orders.csv vào ./data/"
fi

echo ""

# ============================================
# 10. TEST INSTALLATION
# ============================================

echo " Bước 10: Kiểm tra cài đặt..."
echo ""

echo "   Đang test imports..."

# Test critical imports
python -c "import fastapi; print(' FastAPI OK')"
python -c "import vllm; print(' vLLM OK')"
python -c "import torch; print(' PyTorch OK')"
python -c "import pydantic; print(' Pydantic OK')"
python -c "import pandas; print(' Pandas OK')"

echo ""

# ============================================
# 11. DISPLAY NEXT STEPS
# ============================================

echo "============================================"
echo "Setup hoàn tất!"
echo "============================================"
echo ""
echo "Các bước tiếp theo:"
echo ""
echo "1. Kiểm tra cấu hình model:"
echo "   nano .env"
echo "   # Đảm bảo MODEL_PATH đúng"
echo ""
echo "2. Thêm tài liệu sản phẩm vào ./documents/"
echo "   - thong_tin_son_2k.txt"
echo "   - thong_tin_son_1k.txt"
echo "   - bang_thong_so_ky_thuat.csv"
echo "   - ..."
echo ""
echo "3. Thêm dữ liệu đơn hàng vào ./data/orders.csv"
echo ""
echo "4. Khởi động server:"
echo "   ./start_server.sh"
echo "   # hoặc:"
echo "   source venv/bin/activate"
echo "   python api_server.py"
echo ""
echo "5. Test API:"
echo "   # Terminal khác:"
echo "   python test_api.py quick-phanloai"
echo ""
echo "6. Truy cập documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "============================================"
echo ""
echo "LƯU Ý:"
echo "- Model phải được load từ: $MODEL_PATH"
echo "- Documents folder: ./documents/"
echo "- Data folder: ./data/"
echo ""

