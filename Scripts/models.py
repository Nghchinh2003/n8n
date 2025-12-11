from pydantic import BaseModel, Field, validator
from typing import Optional, List


# ============================================
# MODELS CHO AGENT REQUEST/RESPONSE
# ============================================

class AgentRequest(BaseModel):
    """Model cho request đến các agent endpoints."""

    input: str = Field(..., min_length=1, max_length=2000, description="Tin nhắn đầu vào từ user")
    session_id: Optional[str] = Field(None, description="Session ID để theo dõi cuộc hội thoại")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature cho sampling")
    max_tokens: Optional[int] = Field(None, ge=1, le=2048, description="Số tokens tối đa cần generate")

    @validator('input')
    def validate_input(cls, v):
        if not v.strip():
            raise ValueError('Input không được rỗng hoặc chỉ có khoảng trắng')
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "input": "Tôi muốn mua sơn",
                "session_id": "user_123",
                "temperature": 0.7,
                "max_tokens": 512
            }
        }


class AgentResponse(BaseModel):
    """Model cho response từ các agent endpoints."""

    output: str = Field(..., description="Câu trả lời được generate từ agent")
    session_id: Optional[str] = Field(None, description="Session ID")
    processing_time: Optional[float] = Field(None, description="Thời gian xử lý tính bằng giây")

    class Config:
        schema_extra = {
            "example": {
                "output": "{\"json\":\"Create_O\"}",
                "session_id": "user_123",
                "processing_time": 0.5
            }
        }


# ============================================
# MODELS CHO BATCH PROCESSING
# ============================================

class BatchRequest(BaseModel):
    """Model cho request batch processing."""

    inputs: List[str] = Field(..., min_items=1, max_items=50, description="Danh sách các tin nhắn đầu vào")
    agent_type: Optional[str] = Field("consulting", description="Loại agent: phanloai, create_order, hoặc consulting")

    @validator('agent_type')
    def validate_agent_type(cls, v):
        allowed = ['phanloai', 'create_order', 'consulting']
        if v not in allowed:
            raise ValueError(f'Agent type phải là một trong: {", ".join(allowed)}')
        return v

    @validator('inputs')
    def validate_inputs(cls, v):
        # Loại bỏ các string rỗng
        return [s.strip() for s in v if s.strip()]

    class Config:
        schema_extra = {
            "example": {
                "inputs": ["Tôi muốn mua sơn", "Giá sơn nước bao nhiêu?"],
                "agent_type": "consulting"
            }
        }


class BatchResponse(BaseModel):
    """Model cho response từ batch processing."""

    outputs: List[str] = Field(..., description="Danh sách các câu trả lời được generate")
    processing_time: float = Field(..., description="Tổng thời gian xử lý tính bằng giây")

    class Config:
        schema_extra = {
            "example": {
                "outputs": ["Câu trả lời 1", "Câu trả lời 2"],
                "processing_time": 1.2
            }
        }


# ============================================
# MODELS TƯƠNG THÍCH VỚI OPENAI
# ============================================

class OpenAIMessage(BaseModel):
    """Model cho message theo format OpenAI."""

    role: str = Field(..., description="Vai trò của message: system, user, hoặc assistant")
    content: str = Field(..., description="Nội dung message")

    @validator('role')
    def validate_role(cls, v):
        if v not in ['system', 'user', 'assistant']:
            raise ValueError('Role phải là system, user, hoặc assistant')
        return v

    class Config:
        schema_extra = {
            "example": {
                "role": "user",
                "content": "Xin chào"
            }
        }


class OpenAIRequest(BaseModel):
    """Model cho request chat completion theo format OpenAI."""

    messages: List[OpenAIMessage] = Field(..., min_items=1, description="Danh sách các messages")
    model: Optional[str] = Field("llama3.1-agent", description="Tên model")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Temperature cho sampling")
    max_tokens: Optional[int] = Field(512, ge=1, le=2048, description="Số tokens tối đa cần generate")

    class Config:
        schema_extra = {
            "example": {
                "messages": [
                    {"role": "system", "content": "Bạn là AI trợ lý"},
                    {"role": "user", "content": "Xin chào"}
                ],
                "model": "llama3.1-agent",
                "temperature": 0.7,
                "max_tokens": 512
            }
        }


class OpenAIResponse(BaseModel):
    """Model cho response chat completion theo format OpenAI."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[dict]
    usage: Optional[dict] = None

    class Config:
        schema_extra = {
            "example": {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "llama3.1-agent",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Xin chào! Tôi có thể giúp gì cho bạn?"
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }
        }


# ============================================
# MODELS CHO MEMORY
# ============================================

class MemoryResponse(BaseModel):
    """Model cho response từ các memory endpoints."""

    session_id: str
    agent: str
    message_count: int
    messages: List[dict]

    class Config:
        schema_extra = {
            "example": {
                "session_id": "user_123",
                "agent": "consulting",
                "message_count": 5,
                "messages": [
                    {
                        "role": "user",
                        "content": "Xin chào",
                        "timestamp": "2024-11-29T10:00:00"
                    }
                ]
            }
        }


# ============================================
# MODELS CHO HEALTH CHECK
# ============================================

class HealthResponse(BaseModel):
    """Model cho response từ health check endpoint."""

    status: str
    model: str
    backend: str = "vLLM"
    active_sessions: int
    config: Optional[dict] = None

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "model": "VTSNLP/Llama3-ViettelSolutions-8B",
                "backend": "vLLM",
                "active_sessions": 5,
                "config": {
                    "gpu_memory": 0.80,
                    "max_model_len": 4096,
                    "max_num_seqs": 4
                }
            }
        }