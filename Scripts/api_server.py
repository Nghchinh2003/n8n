"""
api_server.py
FastAPI server với spreadsheet_id động cho CHECK_ORDER
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uvicorn
import logging
import json
import os

from config import Config
from models import AgentRequest, AgentResponse
from model_handler import ModelHandler
from agents import AgentService
from memory_manager import MemoryManager
from document_handler import DocumentHandler, create_sample_documents_structure

# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api_server.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# FASTAPI INIT
# ============================================

app = FastAPI(
    title="Multi-Agent LLM API",
    description="API với 4 agents: PhanLoai, CreateOrder, Consulting, CheckOrder",
    version="2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# CUSTOM REQUEST MODELS
# ============================================

class CheckOrderRequest(BaseModel):
    """Request cho check_order với spreadsheet_id động."""
    input: str = Field(..., description="Mã đơn / SĐT / Tên khách")
    session_id: Optional[str] = Field(None, description="Session ID")
    spreadsheet_id: str = Field(..., description="Google Sheets ID (BẮT BUỘC)")
    
    class Config:
        schema_extra = {
            "example": {
                "input": "C21102025",
                "session_id": "user_123",
                "spreadsheet_id": "1a2b3c4d5e6f7g8h9i0j"
            }
        }

# ============================================
# EXCEPTION HANDLERS
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Lỗi: {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Lỗi server nội bộ", "type": str(type(exc).__name__)}
    )

# ============================================
# MIDDLEWARE
# ============================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"← {request.method} {request.url.path} - {response.status_code} ({duration:.2f}s)")
    return response

# ============================================
# KHỞI TẠO SERVICES
# ============================================

logger.info("="*80)
logger.info("🚀 Đang khởi tạo Multi-Agent System...")
logger.info("="*80)

# 1. Model Handler
logger.info("\n📦 Loading Model...")
model_handler = ModelHandler()

# 2. Document Handler (BẮT BUỘC cho CONSULTING)
logger.info("\n📚 Loading Document Handler...")
document_handler = None
try:
    if not os.path.exists("./documents"):
        logger.info("📁 Tạo folder documents và file mẫu...")
        create_sample_documents_structure()
    
    document_handler = DocumentHandler(documents_dir="./documents")
    document_handler.load_all_documents()
    
    logger.info(f"✅ Document Handler: {len(document_handler.documents)} tài liệu, {len(document_handler.products_cache)} sản phẩm")
    
except Exception as e:
    logger.error(f"❌ Document Handler thất bại: {e}")
    logger.error("❌ CONSULTING SẼ KHÔNG HOẠT ĐỘNG ĐÚNG!")

# 3. Agent Service (với Google Sheets credentials)
logger.info("\n🤖 Initializing Agent Service...")

credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
if not os.path.exists(credentials_path):
    logger.warning("⚠️ Không tìm thấy credentials.json")
    logger.warning("⚠️ CHECK_ORDER sẽ KHÔNG hoạt động")
    credentials_path = None

agent_service = AgentService(
    model_handler=model_handler,
    document_handler=document_handler,
    google_sheets_credentials=credentials_path
)

# 4. Memory Manager
memory_manager = MemoryManager()

logger.info("\n" + "="*80)
logger.info("✅ Server sẵn sàng!")
logger.info(f"📊 Tính năng:")
logger.info(f"   - PhanLoai: ✅ Enabled")
logger.info(f"   - CreateOrder: ✅ Enabled")
logger.info(f"   - Consulting: {'✅ Enabled' if document_handler else '❌ Disabled (thiếu documents)'}")
logger.info(f"   - CheckOrder: {'✅ Enabled' if credentials_path else '❌ Disabled (thiếu credentials)'}")
logger.info("="*80 + "\n")

# ============================================
# ENDPOINTS
# ============================================

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "Multi-Agent LLM API",
        "version": "2.0",
        "status": "running",
        "features": {
            "phanloai": "✅ Enabled",
            "create_order": "✅ Enabled",
            "consulting": "✅ Enabled" if document_handler else "❌ Disabled",
            "check_order": "✅ Enabled" if credentials_path else "❌ Disabled"
        },
        "endpoints": {
            "POST /agent/phanloai": "Phân loại ý định (Create_O/Check_O/Unknown)",
            "POST /agent/create_order": "Tạo đơn hàng (thu thập thông tin từng bước)",
            "POST /agent/consulting": "Tư vấn sản phẩm (dựa trên tài liệu)",
            "POST /agent/check_order": "Tra cứu đơn hàng (Google Sheets)",
            "GET /memory/{session_id}": "Lấy lịch sử hội thoại",
            "GET /health": "Health check"
        },
        "documentation": "/docs"
    }

# ============================================
# AGENT 1: PHÂN LOẠI
# ============================================

@app.post("/agent/phanloai", response_model=AgentResponse)
async def phanloai_endpoint(request: AgentRequest):
    """
    🎯 Agent Phân Loại
    
    Phân loại ý định: Create_O, Check_O, Unknown
    """
    try:
        start_time = datetime.now()
        
        history = memory_manager.get_history(request.session_id, agent='phanloai')
        output = agent_service.phanloai_agent(request.input, history)
        
        # Validate JSON
        try:
            json.loads(output)
        except json.JSONDecodeError:
            output = '{"json":"Unknown"}'
        
        if request.session_id:
            memory_manager.add_message(request.session_id, 'phanloai', 'user', request.input)
            memory_manager.add_message(request.session_id, 'phanloai', 'assistant', output)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return AgentResponse(
            output=output,
            session_id=request.session_id,
            processing_time=duration
        )
        
    except Exception as e:
        logger.error(f"Lỗi PhanLoai: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# AGENT 2: TẠO ĐƠN HÀNG
# ============================================

@app.post("/agent/create_order", response_model=AgentResponse)
async def create_order_endpoint(request: AgentRequest):
    """
    📦 Agent Tạo Đơn Hàng
    
    Thu thập: Tên, SĐT, Địa chỉ, Đơn hàng
    Xuất JSON khi đã xác nhận
    """
    try:
        start_time = datetime.now()
        
        history = memory_manager.get_history(request.session_id, agent='create_order')
        output = agent_service.create_order_agent(request.input, history)
        
        if request.session_id:
            memory_manager.add_message(request.session_id, 'create_order', 'user', request.input)
            memory_manager.add_message(request.session_id, 'create_order', 'assistant', output)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return AgentResponse(
            output=output,
            session_id=request.session_id,
            processing_time=duration
        )
        
    except Exception as e:
        logger.error(f"Lỗi CreateOrder: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# AGENT 3: TƯ VẤN
# ============================================

@app.post("/agent/consulting", response_model=AgentResponse)
async def consulting_endpoint(request: AgentRequest):
    """
    🤖 Agent Tư Vấn (✅ WITH SMART DOCUMENTS)
    
    Tư vấn khách hàng về sản phẩm và dịch vụ
    Có khả năng tham khảo tài liệu sản phẩm thông minh
    """
    try:
        start_time = datetime.now()
        
        # Lấy lịch sử cho agent này
        history = memory_manager.get_history(request.session_id, agent='consulting')
        
        # ✅ Generate response với session_id (để track context)
        output = agent_service.consulting_agent(
            user_input=request.input,
            conversation_history=history,
            customer_id=request.session_id,
            session_id=request.session_id  # ← Thêm param này
        )
        
        # Lưu vào memory
        if request.session_id:
            memory_manager.add_message(request.session_id, 'consulting', 'user', request.input)
            memory_manager.add_message(request.session_id, 'consulting', 'assistant', output)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return AgentResponse(
            output=output,
            session_id=request.session_id,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Lỗi Consulting: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# AGENT 4: KIỂM TRA ĐƠN HÀNG
# ============================================

@app.post("/agent/check_order", response_model=AgentResponse)
async def check_order_endpoint(request: CheckOrderRequest):
    """
    🔍 Agent Kiểm Tra Đơn Hàng
    
    Tra cứu từ Google Sheets
    
    **BẮT BUỘC:** spreadsheet_id
    """
    try:
        if not agent_service.sheets_handler:
            raise HTTPException(
                status_code=503,
                detail="Tính năng tra cứu đơn hàng chưa sẵn sàng (thiếu credentials.json)"
            )
        
        start_time = datetime.now()
        
        history = memory_manager.get_history(request.session_id, agent='check_order')
        
        # ✅ Truyền spreadsheet_id vào agent
        output = agent_service.check_order_agent(
            user_input=request.input,
            conversation_history=history,
            spreadsheet_id=request.spreadsheet_id
        )
        
        if request.session_id:
            memory_manager.add_message(request.session_id, 'check_order', 'user', request.input)
            memory_manager.add_message(request.session_id, 'check_order', 'assistant', output)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return AgentResponse(
            output=output,
            session_id=request.session_id,
            processing_time=duration
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi CheckOrder: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# MEMORY ENDPOINTS
# ============================================

@app.get("/memory/{session_id}")
async def get_memory(session_id: str):
    """Lấy lịch sử hội thoại tất cả agents."""
    try:
        info = memory_manager.get_session_info(session_id)
        if not info['exists']:
            raise HTTPException(status_code=404, detail="Session không tồn tại")
        
        result = {"session_id": session_id, "agents": {}}
        
        for agent in ['phanloai', 'create_order', 'consulting', 'check_order']:
            history = memory_manager.get_history(session_id, agent)
            result["agents"][agent] = {
                "message_count": len(history),
                "messages": history
            }
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memory/{session_id}")
async def clear_memory(session_id: str):
    """Xóa lịch sử hội thoại."""
    try:
        success = memory_manager.clear_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session không tồn tại")
        return {"message": f"Đã xóa memory cho session {session_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# SYSTEM ENDPOINTS
# ============================================

@app.get("/health")
def health():
    """Health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model": Config.MODEL_PATH,
        "agents": {
            "phanloai": "✅",
            "create_order": "✅",
            "consulting": "✅" if document_handler else "❌",
            "check_order": "✅" if agent_service.sheets_handler else "❌"
        },
        "resources": {
            "documents": len(document_handler.documents) if document_handler else 0,
            "products": len(document_handler.products_cache) if document_handler else 0,
            "active_sessions": memory_manager.get_active_sessions()
        }
    }

# ============================================
# STARTUP/SHUTDOWN
# ============================================

@app.on_event("startup")
async def startup():
    logger.info("🟢 Server đã khởi động")
    logger.info(f"📡 Listening on http://{Config.HOST}:{Config.PORT}")

@app.on_event("shutdown")
async def shutdown():
    logger.info("🔴 Server đang tắt...")

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level=Config.LOG_LEVEL.lower()
    )