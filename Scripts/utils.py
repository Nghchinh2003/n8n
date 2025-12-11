import re
import json
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================
# TRÍCH XUẤT JSON
# ============================================

def extract_json_from_response(response: str) -> str:
    """
    Trích xuất JSON object từ response của model (cho agent PhanLoai).

    Thử nhiều phương pháp để extract JSON, với validation nghiêm ngặt.
    Nếu không tìm thấy JSON hợp lệ, trả về default {"json":"Unknown"}.

    Args:
        response: Response thô từ model

    Returns:
        Chuỗi JSON hợp lệ với format {"json":"<value>"}
    """
    if not response:
        logger.warning("Response rỗng, trả về Unknown")
        return '{"json":"Unknown"}'

    # Làm sạch response - loại bỏ special tokens của Llama 3 nếu có
    response = response.replace('<|eot_id|>', '').replace('<|end_of_text|>', '').strip()

    # Phương pháp 1: Tìm JSON object hoàn chỉnh với key "json"
    # Pattern khớp với multiline JSON
    pattern = re.compile(
        r'\{[\s\S]*?"json"\s*:\s*"(Create_O|Check_O|Unknown)"[\s\S]*?\}',
        re.IGNORECASE
    )
    match = pattern.search(response)

    if match:
        json_str = match.group(0)
        try:
            # Validate đây là JSON hợp lệ
            parsed = json.loads(json_str)
            # Đảm bảo có cấu trúc đúng
            if 'json' in parsed and parsed['json'] in ['Create_O', 'Check_O', 'Unknown']:
                logger.debug(f"✅ Đã trích xuất JSON (phương pháp 1): {json_str}")
                return json_str
        except json.JSONDecodeError:
            logger.warning(f"⚠️ JSON không hợp lệ được tìm thấy (phương pháp 1): {json_str}")

    # Phương pháp 2: Tìm chỉ key-value pair
    value_pattern = re.compile(r'"json"\s*:\s*"(Create_O|Check_O|Unknown)"', re.IGNORECASE)
    match = value_pattern.search(response)

    if match:
        value = match.group(1)
        result = f'{{"json":"{value}"}}'
        logger.debug(f"✅ Đã trích xuất JSON (phương pháp 2): {result}")
        return result

    # Phương pháp 3: Kiểm tra nếu response chỉ là value (response rất ngắn)
    response_clean = response.strip().strip('`').strip('"').strip("'").strip()

    if response_clean in ['Create_O', 'Check_O', 'Unknown']:
        result = f'{{"json":"{response_clean}"}}'
        logger.debug(f"✅ Đã trích xuất JSON (phương pháp 3): {result}")
        return result

    # Phương pháp 4: Tìm các biến thể viết thường/in hoa
    response_upper = response_clean.upper()
    if response_upper in ['CREATE_O', 'CHECK_O', 'UNKNOWN']:
        # Chuẩn hóa về format đúng
        normalized = 'Create_O' if response_upper == 'CREATE_O' else \
                    'Check_O' if response_upper == 'CHECK_O' else 'Unknown'
        result = f'{{"json":"{normalized}"}}'
        logger.debug(f"✅ Đã trích xuất JSON (phương pháp 4): {result}")
        return result

    # Phương pháp 5: Thử tìm bất kỳ JSON object nào
    try:
        start = response.find('{')
        end = response.rfind('}') + 1

        if start != -1 and end > start:
            json_str = response[start:end]
            parsed = json.loads(json_str)

            if 'json' in parsed and isinstance(parsed['json'], str):
                # Validate giá trị (case-insensitive)
                value = parsed['json']
                if value.upper() in ['CREATE_O', 'CHECK_O', 'UNKNOWN']:
                    # Chuẩn hóa
                    normalized = 'Create_O' if value.upper() == 'CREATE_O' else \
                                'Check_O' if value.upper() == 'CHECK_O' else 'Unknown'
                    result = f'{{"json":"{normalized}"}}'
                    logger.debug(f"✅ Đã trích xuất JSON (phương pháp 5): {result}")
                    return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"⚠️ Phương pháp 5 thất bại: {e}")

    # Fallback mặc định
    logger.warning(f"❌ Không thể trích xuất JSON hợp lệ từ response: {response[:200]}...")
    return '{"json":"Unknown"}'


# ============================================
# FORMAT PROMPT - LLAMA 3 (ĐÚNG CHUẨN)
# ============================================

def format_llama3_prompt(system_prompt: str, messages: List[Dict]) -> str:
    prompt = "<|begin_of_text|>\n"

    # System prompt
    if system_prompt:
        prompt += "<|start_header_id|>system<|end_header_id|>\n"
        prompt += system_prompt.strip() + "\n"
        prompt += "<|eot_id|>\n"

    # Messages
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()

        prompt += f"<|start_header_id|>{role}<|end_header_id|>\n"
        prompt += content + "\n"
        prompt += "<|eot_id|>\n"

    # If last is user → add assistant header
    if messages and messages[-1].get("role") == "user":
        prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

    return prompt





# ============================================
# CÁC HÀM VALIDATION
# ============================================

def validate_phone_number(phone: str) -> bool:
    """
    Validate số điện thoại Việt Nam.

    Chấp nhận các format:
    - 10 số bắt đầu bằng 0: 0912345678
    - Có dấu cách/gạch ngang: 091-234-5678 hoặc 091 234 5678
    - Có mã vùng +84: +84912345678

    Args:
        phone: Chuỗi số điện thoại

    Returns:
        True nếu format hợp lệ, False nếu không
    """
    if not phone:
        return False
    
    # Loại bỏ khoảng trắng, dấu gạch, dấu chấm
    phone_clean = re.sub(r'[\s\-\.]', '', phone)
    
    # Xử lý số có +84
    if phone_clean.startswith('+84'):
        phone_clean = '0' + phone_clean[3:]
    elif phone_clean.startswith('84') and len(phone_clean) == 11:
        phone_clean = '0' + phone_clean[2:]
    
    # Kiểm tra format số điện thoại Việt Nam (10 số bắt đầu bằng 0)
    # Đầu số hợp lệ: 03, 05, 07, 08, 09
    pattern = r'^0[3|5|7|8|9]\d{8}$'
    
    is_valid = bool(re.match(pattern, phone_clean))
    
    if not is_valid:
        logger.debug(f"⚠️ Số điện thoại không hợp lệ: {phone} (cleaned: {phone_clean})")
    
    return is_valid


def validate_json_structure(json_str: str, required_keys: List[str]) -> bool:
    """
    Validate chuỗi JSON có các keys bắt buộc.

    Args:
        json_str: Chuỗi JSON cần validate
        required_keys: List các key names bắt buộc

    Returns:
        True nếu hợp lệ, False nếu không
    """
    try:
        data = json.loads(json_str)
        
        # Kiểm tra tất cả required keys có tồn tại
        missing_keys = [key for key in required_keys if key not in data]
        
        if missing_keys:
            logger.warning(f"⚠️ JSON thiếu keys: {missing_keys}")
            return False
        
        return True
        
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"⚠️ JSON không hợp lệ: {e}")
        return False


def sanitize_text(text: str, max_length: int = 2000) -> str:
    """
    Làm sạch và chuẩn hóa text input.

    Args:
        text: Text đầu vào
        max_length: Độ dài tối đa

    Returns:
        Text đã được làm sạch
    """
    if not text:
        return ""
    
    # Loại bỏ null bytes
    text = text.replace('\x00', '')
    
    # Loại bỏ special tokens của Llama 3 nếu có
    text = text.replace('<|begin_of_text|>', '')
    text = text.replace('<|start_header_id|>', '')
    text = text.replace('<|end_header_id|>', '')
    text = text.replace('<|eot_id|>', '')
    text = text.replace('<|end_of_text|>', '')
    
    # Loại bỏ khoảng trắng thừa (nhiều spaces thành 1 space)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Cắt ngắn nếu quá dài
    if len(text) > max_length:
        text = text[:max_length]
        logger.warning(f"⚠️ Text đã được cắt ngắn về {max_length} ký tự")
    
    return text


# ============================================
# TẠO MÃ ĐƠN HÀNG
# ============================================

def generate_order_code(name: str, phone: str) -> str:
    """
    Tạo mã đơn hàng từ thông tin khách hàng.

    Format: YYYYMMDD-<ChữCáiĐầu>-<3SốCuối>
    Ví dụ: 20241203-N-789 (cho Nguyễn Văn A, SĐT 0123456789)

    Args:
        name: Tên khách hàng
        phone: Số điện thoại

    Returns:
        Chuỗi mã đơn hàng
    """
    # Lấy ngày hiện tại
    date_str = datetime.now().strftime("%Y%m%d")
    
    # Lấy chữ cái đầu của tên (viết hoa)
    # Xử lý tên tiếng Việt có dấu
    name_clean = sanitize_text(name)
    first_letter = 'X'  # Default
    
    if name_clean:
        # Lấy ký tự đầu tiên không phải khoảng trắng
        for char in name_clean:
            if char.isalpha():
                first_letter = char.upper()
                break
    
    # Lấy 3 số cuối của số điện thoại
    phone_clean = re.sub(r'\D', '', phone)  # Loại bỏ ký tự không phải số
    last_3 = phone_clean[-3:] if len(phone_clean) >= 3 else '000'
    
    order_code = f"{date_str}-{first_letter}-{last_3}"
    
    logger.debug(f"✅ Đã tạo mã đơn hàng: {order_code}")
    
    return order_code


# ============================================
# XỬ LÝ TEXT - TRÍCH XUẤT THÔNG TIN
# ============================================

def extract_items_from_text(text: str) -> List[Dict]:
    """
    Cố gắng trích xuất các sản phẩm từ text tự do.
    Đây là extractor dựa trên heuristic đơn giản.

    Ví dụ input: "2 lon sơn dầu trắng 3kg và 5 thùng keo dán"
    Output: [
        {'quantity': 2, 'unit': 'lon', 'description': 'sơn dầu trắng 3kg'},
        {'quantity': 5, 'unit': 'thùng', 'description': 'keo dán'}
    ]

    Args:
        text: Text tự do mô tả sản phẩm

    Returns:
        List các item dicts (có thể rỗng nếu extraction thất bại)
    """
    items = []
    
    if not text:
        return items
    
    # Patterns để khớp với các format phổ biến
    # Format: <số> <đơn vị> <mô tả>
    patterns = [
        # Pattern 1: "2 lon sơn dầu"
        r'(\d+)\s*(lon|thùng|kết|bao|kg|lít|l|túi|hộp|chai|gói)\s+([^,\n]+?)(?=\d+\s*(?:lon|thùng|kết|bao|kg|lít|l|túi|hộp|chai|gói)|và|$)',
        # Pattern 2: "sơn dầu 2 lon"
        r'([^,\n]+?)\s+(\d+)\s*(lon|thùng|kết|bao|kg|lít|l|túi|hộp|chai|gói)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            try:
                groups = match.groups()
                
                # Xác định vị trí của quantity, unit, description
                if groups[0].isdigit():
                    # Pattern 1: quantity đầu tiên
                    quantity = int(groups[0])
                    unit = groups[1]
                    description = groups[2].strip()
                else:
                    # Pattern 2: description đầu tiên
                    description = groups[0].strip()
                    quantity = int(groups[1])
                    unit = groups[2]
                
                # Validate
                if quantity > 0 and description:
                    items.append({
                        'quantity': quantity,
                        'unit': unit.lower(),
                        'description': description
                    })
            except (ValueError, IndexError) as e:
                logger.debug(f"⚠️ Lỗi parse item: {e}")
                continue
    
    # Loại bỏ duplicates
    unique_items = []
    seen = set()
    
    for item in items:
        key = (item['quantity'], item['unit'], item['description'])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    
    logger.debug(f"✅ Đã trích xuất {len(unique_items)} sản phẩm từ text")
    
    return unique_items


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Cắt ngắn chuỗi về độ dài tối đa với suffix.

    Args:
        text: Text đầu vào
        max_length: Độ dài tối đa bao gồm suffix
        suffix: Suffix để thêm nếu bị cắt ngắn

    Returns:
        Chuỗi đã được cắt ngắn
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Đảm bảo max_length > len(suffix)
    if max_length <= len(suffix):
        return suffix[:max_length]
    
    return text[:max_length - len(suffix)] + suffix


# ============================================
# PARSE JSON AN TOÀN
# ============================================

def safe_json_loads(json_str: str, default: any = None) -> any:
    """
    Parse JSON một cách an toàn với fallback.

    Args:
        json_str: Chuỗi JSON cần parse
        default: Giá trị mặc định nếu parse thất bại

    Returns:
        Parsed data hoặc default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"⚠️ Lỗi parse JSON: {e}")
        return default


def safe_json_dumps(data: any, default: str = "{}") -> str:
    """
    Convert data sang JSON string một cách an toàn.

    Args:
        data: Data cần convert
        default: Giá trị mặc định nếu convert thất bại

    Returns:
        JSON string hoặc default value
    """
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as e:
        logger.warning(f"⚠️ Lỗi convert sang JSON: {e}")
        return default


# ============================================
# UTILITIES CHO DEBUG
# ============================================

def log_prompt_preview(prompt: str, max_lines: int = 10):
    """
    Log preview của prompt để debug (hiển thị special tokens).

    Args:
        prompt: Prompt cần preview
        max_lines: Số dòng tối đa để hiển thị
    """
    lines = prompt.split('\n')
    preview_lines = lines[:max_lines]
    
    logger.debug("=" * 50)
    logger.debug("PROMPT PREVIEW:")
    logger.debug("=" * 50)
    
    for i, line in enumerate(preview_lines, 1):
        logger.debug(f"{i:2d} | {line}")
    
    if len(lines) > max_lines:
        logger.debug(f"... ({len(lines) - max_lines} dòng còn lại)")
    
    logger.debug("=" * 50)


def count_tokens_estimate(text: str) -> int:
    """
    Ước tính số tokens trong text (rough estimate).
    
    Llama tokenizer trung bình ~1.3 tokens per word cho tiếng Việt.

    Args:
        text: Text cần đếm

    Returns:
        Số tokens ước tính
    """
    if not text:
        return 0
    
    # Đếm words (split by whitespace)
    words = len(text.split())
    
    # Ước tính: 1.3 tokens per word cho tiếng Việt
    estimated_tokens = int(words * 1.3)
    
    return estimated_tokens