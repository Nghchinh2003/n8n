from typing import List, Dict, Optional
from model_handler import ModelHandler
from prompts import AgentPrompts
from config import Config
from utils import extract_json_from_response, generate_order_code, validate_phone_number
from document_handler import DocumentHandler
from check_order_googlesheets import GoogleSheetsOrderHandler
import json
import re
import logging

logger = logging.getLogger(__name__)


class AgentService:
    """Service quản lý các agents - N8N COMPATIBLE VERSION."""

    def __init__(
        self,
        model_handler: ModelHandler,
        document_handler: Optional[DocumentHandler] = None,
        customer_profile_manager: Optional[CustomerProfileManager] = None,
        order_data_handler: Optional[OrderDataHandler] = None
):
    """Khởi tạo agent service."""
    self.model = model_handler
    self.prompts = AgentPrompts()

    # Tính năng mở rộng
    self.doc_handler = document_handler
    
    # ✅ QUAN TRỌNG: Wrap document_handler với SmartDocumentHandler
    if self.doc_handler:
        self.smart_doc_handler = SmartDocumentHandler(
            base_handler=self.doc_handler,
            model_handler=self.model  # ← Pass model để LLM có thể phân tích
        )
        logger.info("✅ Smart Document Handler: Enabled")
    else:
        self.smart_doc_handler = None
    
    self.customer_manager = customer_profile_manager
    self.order_handler = order_data_handler

    logger.info("Agent Service đã được khởi tạo")
    # ============================================
    # AGENT 1: PHÂN LOẠI 
     def phanloai_agent(
            self,
            user_input: str,
            conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """Agent phân loại - Returns JSON string."""
        logger.info(f"PhanLoai: {user_input[:50]}...")

        try:
            response = self.model.generate(
                system_prompt=self.prompts.PHANLOAI,
                user_input=user_input,
                conversation_history=conversation_history,
                temperature=Config.PHANLOAI_TEMPERATURE,
                max_tokens=Config.PHANLOAI_MAX_TOKENS,
            )

            json_result = extract_json_from_response(response)
            logger.info(f"Kết quả: {json_result}")
            return json_result

        except Exception as e:
            logger.error(f"Lỗi PhanLoai: {e}", exc_info=True)
            return '{"json":"Unknown"}'

    # ============================================
    # AGENT 2: TẠO ĐƠN HÀNG 
    def create_order_agent(
            self,
            user_input: str,
            conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Agent tạo đơn hàng - Returns TEXT hoặc JSON.
        
        n8n workflow expects:
        - Đang thu thập: "Dạ, cho em xin tên..."
        - Đã confirm: "Cảm ơn quý khách...\\nMã đơn: ...\\n..."
        """
        logger.info(f"CreateOrder: {user_input[:50]}...")

        try:
            response = self.model.generate(
                system_prompt=self.prompts.CREATE_ORDER,
                user_input=user_input,
                conversation_history=conversation_history,
                temperature=0.7,
                max_tokens=512,
            )

            # ✅ Kiểm tra xem có phải JSON confirmed không
            if self._is_order_confirmed_json(response):
                try:
                    order_data = json.loads(response)
                    
                    # Validate fields
                    required = ['customer_name', 'phone', 'address', 'items']
                    if all(field in order_data for field in required):
                        # Tạo order_code nếu chưa có
                        if 'order_code' not in order_data:
                            order_data['order_code'] = generate_order_code(
                                order_data['customer_name'],
                                order_data['phone']
                            )
                        
                        # ✅ FORMAT THÀNH TEXT CHO n8n
                        text_output = self._format_order_confirmation_text(order_data)
                        logger.info(f"✅ Đơn hàng confirmed: {order_data['order_code']}")
                        return text_output
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON không hợp lệ: {e}")
            
            # ✅ Loại bỏ hallucination
            response_lower = response.lower()
            bad_patterns = ['hết hàng', 'không còn', 'tạm hết', 'out of stock']
            
            if any(p in response_lower for p in bad_patterns):
                logger.warning(f"⚠️ Hallucination detected")
                return "Dạ, em sẽ hỗ trợ anh/chị đặt hàng ạ. Cho em xin tên của anh/chị?"

            return response

        except Exception as e:
            logger.error(f"Lỗi CreateOrder: {e}", exc_info=True)
            return "Xin lỗi, em gặp lỗi. Vui lòng thử lại ạ."

    def _is_order_confirmed_json(self, response: str) -> bool:
        """Kiểm tra response có phải JSON confirmed không."""
        try:
            data = json.loads(response)
            return data.get('status') == 'confirmed'
        except:
            return False

    def _format_order_confirmation_text(self, order_data: Dict) -> str:
        """
        Format đơn hàng thành TEXT cho n8n workflow.
        
        n8n workflow expects format:
        Cảm ơn quý khách đã đặt hàng của công ty Sơn Đức Dương
        Mã đơn: 05122024-N-789
        Tên người đặt hàng: Nguyễn Văn A
        Số điện thoại: 0123456789
        Địa chỉ nhận hàng: 123 ABC, Q1, HCM
        Đơn hàng: 2 lon sơn dầu trắng, 1 thùng keo
        """
        text = "Cảm ơn quý khách đã đặt hàng của công ty Sơn Đức Dương\n"
        text += f"Mã đơn: {order_data['order_code']}\n"
        text += f"Tên người đặt hàng: {order_data['customer_name']}\n"
        text += f"Số điện thoại: {order_data['phone']}\n"
        text += f"Địa chỉ nhận hàng: {order_data['address']}\n"
        
        # Format items thành comma-separated string
        items_list = []
        for item in order_data['items']:
            item_str = f"{item['quantity']} {item['unit']} {item['product']}"
            if 'color' in item and item['color']:
                item_str += f" {item['color']}"
            if 'weight' in item and item['weight']:
                item_str += f" {item['weight']}"
            items_list.append(item_str)
        
        text += f"Đơn hàng: {', '.join(items_list)}\n"
        
        return text

    # ============================================
    # AGENT 3: TƯ VẤN (GIỮ NGUYÊN)
    # ============================================
    
    def consulting_agent(
        self,
        user_input: str,
        conversation_history: Optional[List[Dict]] = None,
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None  # ← Thêm param này
) -> str:
    """
    Agent tư vấn với SMART document search.
    
    ✅ Dùng LLM để hiểu câu hỏi
    ✅ Context-aware search
    ✅ Multi-query search
    """
    logger.info(f"Consulting đang xử lý: {user_input[:50]}...")

    try:
        system_prompt = self.prompts.CONSULTING

        # ✅ SMART SEARCH: Dùng LLM để tìm kiếm thông minh
        if self.smart_doc_handler:
            try:
                # Get context-aware information
                relevant_info = self.smart_doc_handler.get_context_aware_info(
                    user_input=user_input,
                    session_id=session_id or customer_id,
                    max_length=2000
                )
                
                system_prompt += relevant_info
                logger.info(f"✅ Added smart search results to prompt ({len(relevant_info)} chars)")
                
            except Exception as e:
                logger.warning(f"⚠️ Smart search failed: {e}, using base knowledge")
                # Thêm disclaimer
                system_prompt += "\n\n⚠️ Không tìm thấy tài liệu. Dùng kiến thức cơ bản.\n"
        
        # Customer context
        if customer_id and self.customer_manager:
            customer_context = self.customer_manager.get_customer_context(customer_id)
            system_prompt = get_customer_aware_prompt(system_prompt, customer_context)

        response = self.model.generate(
            system_prompt=system_prompt,
            user_input=user_input,
            conversation_history=conversation_history,
            temperature=Config.DEFAULT_TEMPERATURE,
            max_tokens=Config.DEFAULT_MAX_TOKENS,
        )

        logger.debug(f"Độ dài response Consulting: {len(response)} ký tự")

        return response

    except Exception as e:
        logger.error(f"Lỗi Consulting: {e}", exc_info=True)
        return "Xin lỗi, tôi gặp lỗi khi tư vấn. Vui lòng hỏi lại."

    def _build_document_context(self, doc_results: List[Dict], product_results: List[Dict]) -> str:
        """Build context từ documents."""
        context = ""
        
        if doc_results:
            context += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            context += "📚 THÔNG TIN TỪ TÀI LIỆU:\n"
            context += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for doc in doc_results:
                context += f"\n[{doc['filename']}]\n{doc['snippet']}\n"
        
        if product_results:
            context += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            context += "🏷️ THÔNG TIN SẢN PHẨM:\n"
            context += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for prod in product_results:
                context += f"\n📦 {prod.get('name', prod.get('id'))}:\n"
                for field in ['type', 'color', 'price', 'weights', 'description']:
                    if field in prod:
                        context += f"   • {field}: {prod[field]}\n"
        
        return context

    # ============================================
    # AGENT 4: CHECK ORDER (GIỮ NGUYÊN)
    # ============================================
    
    def check_order_agent(
            self,
            user_input: str,
            conversation_history: Optional[List[Dict]] = None,
            spreadsheet_id: Optional[str] = None
    ) -> str:
        """Agent check order - Từ Google Sheets."""
        logger.info(f"CheckOrder: {user_input[:50]}, sheet={spreadsheet_id}")

        try:
            if not self.sheets_handler:
                return "Xin lỗi, tính năng tra cứu đơn hàng chưa khả dụng. Vui lòng liên hệ hotline ạ."

            system_prompt = self.prompts.CHECK_ORDER

            # ✅ Tìm trong Google Sheets
            order_info = None
            
            if self._looks_like_order_code(user_input):
                logger.info(f"🔍 Tìm theo mã đơn")
                order_info = self.sheets_handler.search_order(user_input, spreadsheet_id)
            elif self._looks_like_phone(user_input):
                logger.info(f"🔍 Tìm theo SĐT")
                order_info = self.sheets_handler.search_order(user_input, spreadsheet_id)
            else:
                logger.info(f"🔍 Tìm theo tên")
                order_info = self.sheets_handler.search_order(user_input, spreadsheet_id)

            if order_info:
                formatted = self.sheets_handler.format_order_info(order_info)
                system_prompt += "\n\n" + formatted
                logger.info(f"✅ Tìm thấy: {order_info.get('order_code')}")
            else:
                system_prompt += "\n\n⚠️ KHÔNG TÌM THẤY ĐƠN HÀNG."
                logger.warning(f"⚠️ Không tìm thấy: {user_input}")

            response = self.model.generate(
                system_prompt=system_prompt,
                user_input=user_input,
                conversation_history=conversation_history,
                temperature=0.7,
                max_tokens=512,
            )

            return response

        except Exception as e:
            logger.error(f"Lỗi CheckOrder: {e}", exc_info=True)
            return "Xin lỗi, em gặp lỗi khi tra cứu. Vui lòng thử lại ạ."

    def _looks_like_order_code(self, text: str) -> bool:
        """Kiểm tra có phải mã đơn không."""
        pattern1 = r'^C?\d{8}$'
        pattern2 = r'^\d{8}-[A-Z]-\d{3}$'
        return bool(re.match(pattern1, text) or re.match(pattern2, text))

    def _looks_like_phone(self, text: str) -> bool:
        """Kiểm tra có phải SĐT không."""
        clean = re.sub(r'[\s\-\.]', '', text)
        return bool(re.match(r'^0[3|5|7|8|9]\d{8}$', clean))

    # ============================================
    # BATCH PROCESSING
    # ============================================
    
    def batch_process(
            self,
            inputs: List[str],
            agent_type: str = "consulting"
    ) -> List[str]:
        """Batch processing."""
        logger.info(f"Batch: {len(inputs)} inputs, agent={agent_type}")

        if agent_type == "phanloai":
            return [self.phanloai_agent(inp) for inp in inputs]
        elif agent_type == "create_order":
            return [self.create_order_agent(inp) for inp in inputs]
        elif agent_type == "consulting":
            return [self.consulting_agent(inp) for inp in inputs]
        elif agent_type == "check_order":
            return [self.check_order_agent(inp) for inp in inputs]
        else:
            return ["Lỗi: Agent type không hợp lệ"] * len(inputs)