from vllm import LLM, SamplingParams
from typing import List, Dict, Optional
from config import Config
from utils import format_llama3_prompt  
import logging

logger = logging.getLogger(__name__)


class ModelHandler:
    """
    Wrapper class cho vLLM model.

    Xử lý:
    - Load và khởi tạo model
    - Single generation với lịch sử hội thoại
    - Batch generation
    - Error handling và logging
    """

    def __init__(self):
        """Khởi tạo vLLM model với config từ Config class."""
        logger.info("Đang load model với vLLM...")
        logger.info(f"✓ Đường dẫn Model: {Config.MODEL_PATH}")
        logger.info(f"✓ Dtype: {Config.DTYPE}")
        logger.info(f"✓ GPU Memory Utilization: {Config.GPU_MEMORY_UTILIZATION}")
        logger.info(f"✓ Max Model Length: {Config.MAX_MODEL_LEN}")
        logger.info(f"✓ Max Num Seqs: {Config.MAX_NUM_SEQS}")
        logger.info(f"✓ Enforce Eager: {Config.ENFORCE_EAGER}")

        try:
            self.llm = LLM(
                model=Config.MODEL_PATH,
                tensor_parallel_size=Config.TENSOR_PARALLEL_SIZE,
                gpu_memory_utilization=Config.GPU_MEMORY_UTILIZATION,
                max_model_len=Config.MAX_MODEL_LEN,
                trust_remote_code=True,
                dtype=Config.DTYPE,
                enforce_eager=Config.ENFORCE_EAGER,
                max_num_seqs=Config.MAX_NUM_SEQS,
                tokenizer_mode="auto",
            )

            logger.info("=" * 60)
            logger.info("✅ Model đã được load thành công!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Không thể load model: {e}")
            logger.error("Stack trace:", exc_info=True)
            raise RuntimeError(f"Load model thất bại: {e}")

    def _build_simple_prompt(self, system_prompt: str, user_input: str) -> str:
        """
        Build simple prompt cho lightweight generation.
        Không dùng format_llama3_prompt để nhanh hơn.
        """
        return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_input}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

    def generate(
            self,
            system_prompt: str,
            user_input: str,
            conversation_history: Optional[List[Dict]] = None,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate response từ model với hỗ trợ lịch sử hội thoại.

        Args:
            system_prompt: Hướng dẫn system cho agent
            user_input: Message hiện tại từ user
            conversation_history: List các messages trước đó (role, content)
            temperature: Temperature cho sampling (None = dùng default)
            max_tokens: Số tokens tối đa để generate (None = dùng default)

        Returns:
            Text response đã được generate

        Raises:
            Exception: Nếu generation thất bại
        """

        # Sử dụng defaults nếu không được chỉ định
        if temperature is None:
            temperature = Config.DEFAULT_TEMPERATURE
        if max_tokens is None:
            max_tokens = Config.DEFAULT_MAX_TOKENS

        try:
            # ✅ SMART HANDLING: Detect short inputs và dùng lightweight prompt
            user_input_clean = user_input.strip().lower()
            
            # Phân loại intent của short inputs
            greeting_words = ['hi', 'hey', 'hello', 'chào', 'chao', 'xin chào', 'alo', 'a lo', 'hê lô']
            farewell_words = ['bye', 'goodbye', 'tạm biệt', 'tam biet', 'hẹn gặp lại', 'see you', 'bai bai']
            acknowledgment_words = ['ok', 'oke', 'okay', 'uh', 'um', 'uhm', 'à', 'ờ', 'ừ']
            thanks_words = ['thanks', 'thank you', 'cảm ơn', 'cam on', 'cám ơn', 'thank', 'cảm ơn em']
            
            is_greeting = user_input_clean in greeting_words
            is_farewell = user_input_clean in farewell_words
            is_thanks = user_input_clean in thanks_words
            is_acknowledgment = user_input_clean in acknowledgment_words
            
            # ✅ Nếu là short social input → Dùng lightweight prompt
            if is_greeting or is_farewell or is_thanks:
                logger.info(f"🎭 Detected social input: '{user_input}' (type: {is_greeting and 'greeting' or is_farewell and 'farewell' or 'thanks'})")
                
                # Xác định loại
                if is_greeting:
                    intent_type = "greeting (chào hỏi)"
                elif is_farewell:
                    intent_type = "farewell (tạm biệt)"
                else:
                    intent_type = "thanks (cảm ơn)"
                
                # Lightweight prompt - để model tự sáng tạo
                lightweight_system = f"""Bạn là trợ lý thân thiện của Sơn Đức Dương.

Khách vừa {intent_type}. Hãy trả lời TỰ NHIÊN, NGẮN GỌN (1-2 câu).

Gợi ý:
- Nếu chào hỏi: Chào lại thân thiện, hỏi cần giúp gì
- Nếu tạm biệt: Chúc tốt lành, mời quay lại
- Nếu cảm ơn: Đáp lại lịch sự

Xưng "em" (bạn), "anh/chị" (khách). TỰ NHIÊN, đừng giống nhau mỗi lần."""

                # Generate với lightweight prompt
                response = self.llm.generate(
                    [self._build_simple_prompt(lightweight_system, user_input)],
                    SamplingParams(
                        temperature=0.8,  # Cao hơn để đa dạng
                        top_p=0.95,
                        max_tokens=100,
                        stop=["<|eot_id|>", "<|end_of_text|>", "\n\n"]
                    )
                )
                
                text = response[0].outputs[0].text.strip()
                
                if text:
                    logger.info(f"✅ Generated social response: {len(text)} chars")
                    return text
                
                # Fallback nếu generate rỗng
                logger.warning("⚠️ Lightweight generation failed, using fallback")
            
            # ✅ Acknowledgment (ok, oke): Phụ thuộc context
            if is_acknowledgment:
                # Kiểm tra có conversation history không
                if not conversation_history or len(conversation_history) == 0:
                    logger.info(f"❓ Acknowledgment without context: '{user_input}'")
                    
                    # Lightweight prompt cho acknowledgment
                    ack_prompt = """Bạn là trợ lý của Sơn Đức Dương.

Khách chỉ nói "ok/oke" mà không có ngữ cảnh trước đó.

Hãy hỏi lại xem khách cần giúp gì. Tự nhiên, ngắn gọn 1 câu."""
                    
                    response = self.llm.generate(
                        [self._build_simple_prompt(ack_prompt, user_input)],
                        SamplingParams(
                            temperature=0.7,
                            max_tokens=80,
                            stop=["<|eot_id|>", "<|end_of_text|>"]
                        )
                    )
                    
                    text = response[0].outputs[0].text.strip()
                    if text:
                        return text
                else:
                    # Có context → Để xử lý bình thường
                    logger.info(f"✅ Acknowledgment with context, continue normally")
            
            # ✅ Input quá ngắn và không có ý nghĩa
            if len(user_input_clean) <= 2 and user_input_clean not in ['hi', 'ơi', 'à', 'ê']:
                logger.warning(f"⚠️ Input quá ngắn: '{user_input}'")
                
                unclear_prompt = """Bạn là trợ lý của Sơn Đức Dương.

Khách gửi tin nhắn quá ngắn/không rõ ràng.

Hãy lịch sự hỏi lại. Ngắn gọn, tự nhiên."""
                
                response = self.llm.generate(
                    [self._build_simple_prompt(unclear_prompt, user_input)],
                    SamplingParams(
                        temperature=0.7,
                        max_tokens=60,
                        stop=["<|eot_id|>", "<|end_of_text|>"]
                    )
                )
                
                text = response[0].outputs[0].text.strip()
                if text:
                    return text
            
            # ✅ Tiếp tục xử lý bình thường cho các input khác
            # Chuẩn bị lịch sử hội thoại (chỉ giữ các messages gần đây)
            history = []
            if conversation_history:
                # Giữ 10 messages cuối để quản lý độ dài context
                history = conversation_history[-10:]

            # Thêm user message hiện tại
            history.append({"role": "user", "content": user_input})

            # ✅ FIXED: Format prompt với Llama 3 template ĐÚNG CHUẨN
            prompt = format_llama3_prompt(system_prompt, history)

            # Log độ dài prompt
            logger.debug(f"📝 Độ dài prompt: {len(prompt)} ký tự, {len(history)} turns")
            logger.debug(f"📝 Prompt preview (first 300 chars): {prompt[:300]}...")
            
            # Debug: Log toàn bộ prompt nếu cần
            if logger.level <= logging.DEBUG:
                logger.debug("=" * 60)
                logger.debug("FULL PROMPT:")
                logger.debug("=" * 60)
                logger.debug(prompt)
                logger.debug("=" * 60)

            # ✅ FIXED: Stop tokens cho Llama 3
            llama3_stop_tokens = [
                "<|eot_id|>",           # End of turn
                "<|end_of_text|>",      # End of text
                "<|start_header_id|>",  # Không để model tự tạo header mới
            ]

            # Tham số sampling
            sampling_params = SamplingParams(
                temperature=temperature,
                top_p=Config.TOP_P,
                max_tokens=max_tokens,
                repetition_penalty=Config.REPETITION_PENALTY,
                stop=llama3_stop_tokens,  # ✅ FIXED: Dùng stop tokens đúng cho Llama 3
            )

            logger.debug(f"⚙️ Sampling params: temp={temperature}, max_tokens={max_tokens}, top_p={Config.TOP_P}")
            logger.debug(f"⚙️ Stop tokens: {llama3_stop_tokens}")

            # Generate
            logger.debug("🔄 Đang generate...")
            outputs = self.llm.generate([prompt], sampling_params)

            # DEBUG: Log chi tiết output
            logger.info(f"✅ Generated output count: {len(outputs)}")
            
            if outputs and len(outputs) > 0:
                raw_text = outputs[0].outputs[0].text
                finish_reason = outputs[0].outputs[0].finish_reason
                
                logger.info(f"📊 Raw output length: {len(raw_text)} chars")
                logger.info(f"📊 Finish reason: {finish_reason}")
                logger.info(f"📊 Raw output preview (first 500 chars): '{raw_text[:500]}'")
                
                # ✅ FIXED: Làm sạch output
                # Loại bỏ special tokens nếu có
                cleaned_text = raw_text
                for token in llama3_stop_tokens:
                    cleaned_text = cleaned_text.replace(token, '')
                
                cleaned_text = cleaned_text.strip()
                
                # Kiểm tra nếu output rỗng HOẶC chỉ chứa meta-instructions
                if not cleaned_text or len(cleaned_text) == 0:
                    logger.warning("⚠️ Model generate response RỖNG sau khi clean!")
                    return "Xin lỗi, em chưa thể tạo câu trả lời phù hợp. Anh/chị thử hỏi lại được không ạ?"
                
                # ✅ FIXED: Phát hiện meta-instructions
                meta_keywords = [
                    "nếu nhận tag",
                    "ta sẽ trả lời",
                    "ta có thể dựa vào",
                    "để đưa ra câu trả lời",
                    "quy tắc:",
                    "quy_tắc",
                    "nhiệm vụ:",
                    "nhiệm_vụ",
                    "bước 1:",
                    "phương pháp",
                    "ví dụ trả lời",
                    "lưu ý:",
                    "trong đoạn đối thoại",
                    "trên đây là ví dụ",
                    "#1.", "#2.", "#3.", "#4.",  # Headers
                    "quan_trọng:",
                ]
                
                cleaned_lower = cleaned_text.lower()
                has_meta = any(kw in cleaned_lower for kw in meta_keywords)
                
                if has_meta:
                    logger.warning("⚠️ Model đang generate META-INSTRUCTIONS thay vì trả lời!")
                    logger.warning(f"⚠️ Detected keywords in output: {[kw for kw in meta_keywords if kw in cleaned_lower]}")
                    logger.warning(f"⚠️ Output preview: {cleaned_text[:300]}")
                    
                    # Thử extract câu trả lời thực sự (nếu có)
                    # Tìm dòng đầu tiên không phải là instruction
                    lines = cleaned_text.split('\n')
                    for line in lines:
                        line_clean = line.strip()
                        line_lower = line_clean.lower()
                        
                        # Bỏ qua dòng là instruction
                        if any(kw in line_lower for kw in meta_keywords):
                            continue
                        
                        # Bỏ qua dòng rỗng hoặc chỉ có dấu
                        if not line_clean or line_clean in ['-', '*', '•']:
                            continue
                        
                        # Nếu tìm được dòng hợp lệ, trả về
                        if len(line_clean) > 10:
                            logger.info(f"✅ Extracted valid response from meta output: {line_clean[:100]}")
                            return line_clean
                    
                    # Không tìm được câu trả lời hợp lệ
                    return "Chào anh/chị! Em là trợ lý của Sơn Đức Dương. Em có thể giúp gì cho anh/chị ạ?"
                
                logger.info(f"✅ Generated successfully: {len(cleaned_text)} chars")
                logger.debug(f"✅ Final output: {cleaned_text[:200]}...")
                
                return cleaned_text
                
            else:
                logger.error("Model trả về output array rỗng")
                return "Xin lỗi, em gặp lỗi khi xử lý yêu cầu."

        except Exception as e:
            logger.error(f"Lỗi khi generate: {e}", exc_info=True)
            logger.error(f"User input was: {user_input}")
            logger.error(f"System prompt length: {len(system_prompt)}")
            return "Xin lỗi, em gặp lỗi khi xử lý yêu cầu của anh/chị."

    def batch_generate(
            self,
            prompts: List[str],
            system_prompt: str,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
    ) -> List[str]:
        """
        Batch generation cho nhiều prompts cùng lúc.

        Lưu ý: Không sử dụng lịch sử hội thoại - tốt nhất cho các queries đơn giản.

        Args:
            prompts: List các chuỗi user input
            system_prompt: Hướng dẫn system
            temperature: Temperature cho sampling
            max_tokens: Số tokens tối đa mỗi generation

        Returns:
            List các responses đã generate (cùng độ dài với prompts)
        """

        # Sử dụng defaults nếu không được chỉ định
        if temperature is None:
            temperature = Config.DEFAULT_TEMPERATURE
        if max_tokens is None:
            max_tokens = Config.DEFAULT_MAX_TOKENS

        try:
            logger.info(f"📦 Đang batch generate {len(prompts)} prompts")

            # Format tất cả prompts với Llama 3 format
            formatted = []
            for p in prompts:
                formatted.append(
                    format_llama3_prompt(  # ✅ FIXED: Dùng format đúng
                        system_prompt,
                        [{"role": "user", "content": p}]
                    )
                )

            # Stop tokens cho Llama 3
            llama3_stop_tokens = [
                "<|eot_id|>",
                "<|end_of_text|>",
                "<|start_header_id|>",
            ]

            # Tham số sampling
            sampling_params = SamplingParams(
                temperature=temperature,
                top_p=Config.TOP_P,
                max_tokens=max_tokens,
                repetition_penalty=Config.REPETITION_PENALTY,
                stop=llama3_stop_tokens,  # ✅ FIXED
            )

            # Generate batch
            outputs = self.llm.generate(formatted, sampling_params)

            # Trích xuất và làm sạch tất cả texts
            results = []
            for o in outputs:
                text = o.outputs[0].text
                # Loại bỏ special tokens
                for token in llama3_stop_tokens:
                    text = text.replace(token, '')
                results.append(text.strip())

            logger.info(f"✅ Batch generation hoàn tất: {len(results)} responses")

            return results

        except Exception as e:
            logger.error(f"❌ Lỗi batch generation: {e}", exc_info=True)
            # Trả về error messages cho tất cả prompts
            return ["Lỗi xử lý"] * len(prompts)

    def get_model_info(self) -> Dict:
        """
        Lấy thông tin về model đang được load.
        
        Returns:
            Dict chứa thông tin model
        """
        return {
            "model_path": Config.MODEL_PATH,
            "dtype": Config.DTYPE,
            "max_model_len": Config.MAX_MODEL_LEN,
            "gpu_memory_utilization": Config.GPU_MEMORY_UTILIZATION,
            "tensor_parallel_size": Config.TENSOR_PARALLEL_SIZE,
            "max_num_seqs": Config.MAX_NUM_SEQS,
        }