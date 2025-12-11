"""
Cấu hình tập trung 
"""

import os


class Config:
    """Cấu hình tập trung cho ứng dụng."""

    MODEL_PATH = os.getenv("MODEL_PATH", "/root/llm-agent-api/Model")

    DTYPE = os.getenv("DTYPE", "auto")

    GPU_MEMORY_UTILIZATION = float(os.getenv("GPU_MEMORY_UTILIZATION", 0.75))

    MAX_MODEL_LEN = int(os.getenv("MAX_MODEL_LEN", 4096))

    # Số GPU sử dụng cho tensor parallel
    # Đặt là 1 cho single GPU (RTX 3090)
    TENSOR_PARALLEL_SIZE = int(os.getenv("TENSOR_PARALLEL_SIZE", 1))

    # Bắt buộc chạy eager execution (tắt CUDA graphs)
    # Đặt False để hiệu suất tốt hơn (chỉ bật True nếu gặp lỗi CUDA)
    ENFORCE_EAGER = os.getenv("ENFORCE_EAGER", "false").lower() in ("1", "true", "yes")

    # Số lượng sequences tối đa trong một batch
    # Cao hơn = throughput tốt hơn nhưng cần nhiều memory hơn
    MAX_NUM_SEQS = int(os.getenv("MAX_NUM_SEQS", 6))

    # ============================================
    # CÀI ĐẶT SERVER
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # Số lượng tin nhắn tối đa lưu trong lịch sử cho mỗi agent mỗi session
    MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", 30))

    # ============================================
    # CÀI ĐẶT GENERATION
    # Tham số generation mặc định
    DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", 0.7))
    # TĂNG MAX_TOKENS LÊN
    DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", 1024))

    # Cài đặt cho agent phân loại - temperature rất thấp để output ổn định
    PHANLOAI_TEMPERATURE = float(os.getenv("PHANLOAI_TEMPERATURE", 0.1))
    PHANLOAI_MAX_TOKENS = int(os.getenv("PHANLOAI_MAX_TOKENS", 64))

    # Tham số sampling
    TOP_P = float(os.getenv("TOP_P", 0.9))
    REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", 1.1))

    # ============================================
    # LOGGING
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")