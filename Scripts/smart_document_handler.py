"""
smart_document_handler.py
Document handler với LLM-powered semantic search
"""

import logging
from typing import List, Dict, Optional
from document_handler import DocumentHandler

logger = logging.getLogger(__name__)


class SmartDocumentHandler:
    """
    Enhanced DocumentHandler với khả năng:
    1. Query rewriting bằng LLM
    2. Context-aware search
    3. Multi-query search
    """
    
    def __init__(
        self,
        base_handler: DocumentHandler,
        model_handler=None  # ModelHandler instance
    ):
        self.base_handler = base_handler
        self.model = model_handler
        self.conversation_context = {}  # Track context per session
    
    def rewrite_query(self, user_input: str, session_id: Optional[str] = None) -> List[str]:
        """
        Dùng LLM để phân tích câu hỏi và tạo multiple search queries.
        
        Args:
            user_input: Câu hỏi từ user
            session_id: Session để track context
            
        Returns:
            List các search queries tối ưu
        """
        if not self.model:
            # Fallback: Không có model, dùng simple keyword extraction
            return self._simple_keyword_extraction(user_input)
        
        # Get context từ câu hỏi trước (nếu có)
        context = ""
        if session_id and session_id in self.conversation_context:
            prev_topic = self.conversation_context[session_id].get('topic')
            if prev_topic:
                context = f"\nCâu hỏi trước đó về: {prev_topic}"
        
        # Prompt cho LLM
        query_rewrite_prompt = f"""Phân tích câu hỏi của khách hàng và trích xuất thông tin tìm kiếm.

Câu hỏi: "{user_input}"{context}

Nhiệm vụ:
1. Xác định chủ đề chính (sản phẩm nào? sơn 2K, sơn 1K, sơn dầu...)
2. Xác định thông tin cần tìm (giá? thành phần? ứng dụng? cách dùng?)
3. Tạo 3-5 search queries ngắn gọn để tìm trong tài liệu

Trả về ĐÚNG format JSON:
{{
  "main_topic": "sơn 2K",
  "question_type": "ứng dụng",
  "search_queries": [
    "sơn 2k",
    "ứng dụng sơn 2k",
    "sơn ngoài trời"
  ],
  "entities": ["sơn 2K", "ngoài trời"]
}}

CHỈ trả về JSON, không giải thích."""

        try:
            response = self.model.generate(
                system_prompt="Bạn là trợ lý phân tích câu hỏi. CHỈ trả về JSON.",
                user_input=query_rewrite_prompt,
                temperature=0.3,
                max_tokens=256
            )
            
            # Parse JSON
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                
                # Lưu context cho lần sau
                if session_id:
                    self.conversation_context[session_id] = {
                        'topic': data.get('main_topic'),
                        'entities': data.get('entities', [])
                    }
                
                queries = data.get('search_queries', [])
                logger.info(f"🔍 Rewritten queries: {queries}")
                return queries
            
        except Exception as e:
            logger.warning(f"⚠️ Query rewriting failed: {e}, using fallback")
        
        # Fallback
        return self._simple_keyword_extraction(user_input)
    
    def _simple_keyword_extraction(self, text: str) -> List[str]:
        """Fallback: Simple keyword extraction."""
        # Remove stop words
        stop_words = {'là', 'gì', 'như', 'thế', 'nào', 'được', 'không', 'có', 'của', 'thì'}
        
        words = text.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Tạo queries
        queries = []
        
        # Full text
        if len(keywords) <= 3:
            queries.append(' '.join(keywords))
        
        # Individual keywords
        for kw in keywords[:3]:
            queries.append(kw)
        
        # Bigrams
        for i in range(len(keywords) - 1):
            queries.append(f"{keywords[i]} {keywords[i+1]}")
        
        return list(set(queries))[:5]  # Max 5 queries
    
    def smart_search(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        limit: int = 5
    ) -> Dict:
        """
        Tìm kiếm thông minh với query rewriting.
        
        Returns:
            Dict với documents và products tìm được
        """
        # 1. Rewrite queries
        queries = self.rewrite_query(user_input, session_id)
        
        logger.info(f"🔍 Searching with {len(queries)} queries: {queries}")
        
        # 2. Search với multiple queries
        all_doc_results = []
        all_product_results = []
        
        seen_docs = set()
        seen_products = set()
        
        for query in queries:
            # Search documents
            docs = self.base_handler.search_in_documents(query, limit=2)
            for doc in docs:
                doc_key = doc['filename']
                if doc_key not in seen_docs:
                    all_doc_results.append(doc)
                    seen_docs.add(doc_key)
            
            # Search products
            products = self.base_handler.search_products(query, limit=2)
            for prod in products:
                prod_key = prod.get('id', prod.get('name'))
                if prod_key not in seen_products:
                    all_product_results.append(prod)
                    seen_products.add(prod_key)
        
        # 3. Sort by relevance
        all_doc_results.sort(key=lambda x: x.get('relevance', 0), reverse=True)
        all_product_results = all_product_results[:limit]
        
        logger.info(f"✅ Found {len(all_doc_results)} docs, {len(all_product_results)} products")
        
        return {
            'documents': all_doc_results[:limit],
            'products': all_product_results,
            'queries_used': queries
        }
    
    def get_context_aware_info(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        max_length: int = 2000
    ) -> str:
        """
        Lấy thông tin với context awareness.
        
        Tương tự get_relevant_context() nhưng thông minh hơn.
        """
        # Smart search
        results = self.smart_search(user_input, session_id, limit=3)
        
        context = ""
        
        # Add documents
        if results['documents']:
            context += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            context += "📚 THÔNG TIN TỪ TÀI LIỆU:\n"
            context += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for doc in results['documents']:
                context += f"\n[{doc['filename']}]\n"
                context += f"{doc['snippet']}\n"
        
        # Add products
        if results['products']:
            context += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            context += "🏷️ THÔNG TIN SẢN PHẨM:\n"
            context += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for prod in results['products']:
                context += f"\n📦 {prod.get('name', prod.get('id'))}:\n"
                
                for field in ['type', 'color', 'price', 'description', 'weights']:
                    if field in prod:
                        context += f"   • {field}: {prod[field]}\n"
        
        # Truncate if too long
        if len(context) > max_length:
            context = context[:max_length] + "\n\n... (Nội dung bị cắt ngắn)"
        
        if not context:
            context = "\n\n⚠️ Không tìm thấy thông tin liên quan trong tài liệu.\n"
        
        return context


# ============================================
# INTEGRATION VỚI AGENTS
# ============================================

def create_smart_handler(base_handler: DocumentHandler, model_handler) -> SmartDocumentHandler:
    """Helper để tạo SmartDocumentHandler."""
    return SmartDocumentHandler(base_handler, model_handler)