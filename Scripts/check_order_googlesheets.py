"""
check_order_googlesheets.py
CheckBot đọc đơn hàng từ Google Sheets với spreadsheet_id động
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class GoogleSheetsOrderHandler:
    """
    Đọc đơn hàng từ Google Sheets với khả năng:
    - Nhận spreadsheet_id động từ API
    - Parse mã đơn hàng để xác định ngày
    - Tìm kiếm đơn hàng theo mã/SĐT/tên
    - Format thông tin đơn hàng
    """
    
    def __init__(self, credentials_file: str = "./credentials.json"):
        """
        Khởi tạo Google Sheets handler.
        
        Args:
            credentials_file: Path đến file credentials.json (Google Service Account)
        """
        self.credentials_file = credentials_file
        self.client = None
        self._init_client()
        
        logger.info("GoogleSheetsOrderHandler đã khởi tạo")
    
    def _init_client(self):
        """Khởi tạo Google Sheets client."""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            if not os.path.exists(self.credentials_file):
                logger.error(f"❌ Không tìm thấy file credentials: {self.credentials_file}")
                self.client = None
                return
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=scopes
            )
            
            self.client = gspread.authorize(creds)
            logger.info("✅ Google Sheets client đã kết nối")
            
        except ImportError:
            logger.error("❌ Cần cài: pip install gspread google-auth")
            self.client = None
        except Exception as e:
            logger.error(f"❌ Lỗi kết nối Google Sheets: {e}")
            self.client = None
    
    def parse_order_code(self, order_code: str) -> Optional[Dict]:
        """
        Parse mã đơn hàng để lấy thông tin ngày.
        
        Format mã đơn: 
        - C21102025 → Ngày: 21, Tháng: 10, Năm: 2025
        - 21102025-N-789 → Tương tự
        
        Args:
            order_code: Mã đơn hàng
            
        Returns:
            Dict {day, month, year, date_str} hoặc None
        """
        # Loại bỏ ký tự không phải số
        numbers = re.sub(r'[^\d]', '', order_code)
        
        # Pattern 1: DDMMYYYY (8 số)
        if len(numbers) >= 8:
            day = int(numbers[0:2])
            month = int(numbers[2:4])
            year = int(numbers[4:8])
            
            # Validate ngày tháng
            if 1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2099:
                return {
                    'day': day,
                    'month': month,
                    'year': year,
                    'date_str': f"{day:02d}/{month:02d}/{year}"
                }
        
        return None
    
    def search_order_in_sheet(
        self,
        spreadsheet_id: str,
        query: str,
        sheet_name: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Tìm đơn hàng trong Google Sheet cụ thể.
        
        Args:
            spreadsheet_id: ID của spreadsheet (VD: "1a2b3c4d5e...")
            query: Mã đơn / SĐT / Tên khách cần tìm
            sheet_name: Tên sheet cụ thể (None = sheet đầu tiên)
            
        Returns:
            Dict chứa thông tin đơn hàng hoặc None
        """
        if not self.client:
            logger.error("❌ Google Sheets client chưa được khởi tạo")
            return None
        
        try:
            # Mở spreadsheet
            logger.info(f"📂 Đang mở spreadsheet: {spreadsheet_id}")
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # Lấy worksheet
            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)  # Sheet đầu tiên
            
            logger.info(f"📄 Đang đọc sheet: {worksheet.title}")
            
            # Lấy tất cả data
            data = worksheet.get_all_records()
            logger.info(f"📊 Đã load {len(data)} rows")
            
            # Chuẩn hóa query
            query_clean = self._normalize_query(query)
            
            # Tìm đơn hàng
            for row in data:
                # Kiểm tra từng trường có thể khớp
                fields_to_check = [
                    'Mã đơn hàng',
                    'order_code',
                    'Số điện thoại',
                    'phone',
                    'Tên',
                    'customer_name'
                ]
                
                for field in fields_to_check:
                    if field in row:
                        value_clean = self._normalize_query(str(row[field]))
                        
                        if query_clean in value_clean or value_clean in query_clean:
                            # Tìm thấy!
                            logger.info(f"✅ Tìm thấy đơn hàng: {row.get('Mã đơn hàng', row.get('order_code'))}")
                            
                            return self._normalize_order_data(row)
            
            logger.warning(f"⚠️ Không tìm thấy đơn hàng với query: {query}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Lỗi tìm đơn hàng: {e}", exc_info=True)
            return None
    
    def _normalize_query(self, text: str) -> str:
        """Chuẩn hóa query để tìm kiếm tốt hơn."""
        # Loại bỏ khoảng trắng, dấu gạch, chuyển lowercase
        return re.sub(r'[\s\-\.]', '', text.lower())
    
    def _normalize_order_data(self, row: Dict) -> Dict:
        """
        Chuẩn hóa dữ liệu đơn hàng từ Google Sheets.
        
        Chuyển đổi các tên cột khác nhau về format thống nhất.
        """
        return {
            'order_code': row.get('Mã đơn hàng', row.get('order_code', 'N/A')),
            'customer_name': row.get('Tên', row.get('customer_name', 'N/A')),
            'phone': row.get('Số điện thoại', row.get('phone', 'N/A')),
            'address': row.get('Địa chỉ', row.get('address', 'N/A')),
            'product': row.get('Đơn hàng', row.get('product', 'N/A')),
            'status': row.get('Trạng thái', row.get('status', 'Đã đặt hàng')),
            'created_at': row.get('Ngày đặt', row.get('created_at', 'N/A')),
            'notes': row.get('Ghi chú', row.get('notes', '')),
            'spreadsheet_id': 'provided'  # Đánh dấu nguồn
        }
    
    def search_order(
        self,
        query: str,
        spreadsheet_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Tìm đơn hàng (smart search).
        
        Flow:
        1. Nếu có spreadsheet_id → Tìm trực tiếp trong sheet đó
        2. Nếu không có → Parse mã đơn để tìm sheet tương ứng (TODO)
        3. Fallback: Tìm trong các sheet gần đây (TODO)
        
        Args:
            query: Mã đơn / SĐT / Tên khách
            spreadsheet_id: ID của spreadsheet cụ thể (nếu có)
            
        Returns:
            Dict chứa thông tin đơn hàng hoặc None
        """
        logger.info(f"🔍 Tìm kiếm đơn hàng: query='{query}', spreadsheet_id={spreadsheet_id}")
        
        # Case 1: Có spreadsheet_id → Tìm trực tiếp
        if spreadsheet_id:
            return self.search_order_in_sheet(spreadsheet_id, query)
        
        # Case 2: Parse mã đơn để tìm spreadsheet tương ứng
        date_info = self.parse_order_code(query)
        
        if date_info:
            logger.info(f"📅 Parsed date: {date_info['date_str']}")
            
            # TODO: Implement logic tìm spreadsheet_id từ ngày
            # Option 1: Có mapping table (date -> spreadsheet_id)
            # Option 2: Naming convention cố định (VD: "Orders_21102025")
            # Option 3: Search trong Google Drive folder
            
            logger.warning("⚠️ Auto-detect spreadsheet từ ngày chưa được implement")
            logger.warning("⚠️ Cần truyền spreadsheet_id từ API")
        
        # Case 3: Fallback - Tìm trong các sheet gần đây
        # TODO: Implement search trong 7 ngày gần nhất
        
        logger.warning("⚠️ Không thể tìm đơn hàng mà không có spreadsheet_id")
        return None
    
    def format_order_info(self, order: Dict) -> str:
        """
        Format thông tin đơn hàng thành text đẹp.
        
        Args:
            order: Dict chứa thông tin đơn hàng
            
        Returns:
            Chuỗi text đã format
        """
        if not order:
            return "⚠️ Không tìm thấy đơn hàng."
        
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 THÔNG TIN ĐƠN HÀNG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔖 Mã đơn: {order.get('order_code', 'N/A')}
👤 Khách hàng: {order.get('customer_name', 'N/A')}
📞 Số điện thoại: {order.get('phone', 'N/A')}
📍 Địa chỉ: {order.get('address', 'N/A')}

📦 Sản phẩm: {order.get('product', 'N/A')}

📊 Trạng thái: {order.get('status', 'Đã đặt hàng')}
📅 Ngày đặt: {order.get('created_at', 'N/A')}

{f"📝 Ghi chú: {order.get('notes')}" if order.get('notes') else ""}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()
    
    def test_connection(self, spreadsheet_id: str) -> bool:
        """
        Test kết nối với Google Sheets.
        
        Args:
            spreadsheet_id: ID của spreadsheet cần test
            
        Returns:
            True nếu kết nối thành công
        """
        if not self.client:
            logger.error("❌ Client chưa được khởi tạo")
            return False
        
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.get_worksheet(0)
            logger.info(f"✅ Test thành công: {spreadsheet.title} / {worksheet.title}")
            return True
        except Exception as e:
            logger.error(f"❌ Test thất bại: {e}")
            return False


# ============================================
# HELPER FUNCTIONS
# ============================================

def create_sample_credentials_guide():
    """Tạo hướng dẫn setup credentials.json"""
    guide = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 HƯỚNG DẪN TẠO CREDENTIALS.JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Truy cập: https://console.cloud.google.com/

2. Tạo hoặc chọn Project

3. Bật API:
   - Google Sheets API
   - Google Drive API

4. Tạo Service Account:
   - IAM & Admin > Service Accounts
   - CREATE SERVICE ACCOUNT
   - Grant role: Editor
   - CREATE KEY → JSON

5. Download file JSON và đổi tên thành "credentials.json"

6. Chia sẻ Google Sheet với email trong credentials.json:
   - Mở file credentials.json
   - Copy email trong field "client_email"
   - Vào Google Sheets → Share → Paste email → Editor

7. Đặt credentials.json vào thư mục dự án

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    print(guide)


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    # Hiển thị hướng dẫn
    create_sample_credentials_guide()
    
    # Test nếu có credentials
    if os.path.exists("./credentials.json"):
        handler = GoogleSheetsOrderHandler()
        
        # Test parse mã đơn
        print("\n=== Test parse mã đơn ===")
        test_codes = ["C21102025", "21102025", "21102025-N-789"]
        for code in test_codes:
            result = handler.parse_order_code(code)
            print(f"{code} → {result}")
        
        # Test connection (cần spreadsheet_id thực)
        print("\n=== Test connection ===")
        test_id = input("Nhập spreadsheet_id để test (Enter để bỏ qua): ").strip()
        if test_id:
            handler.test_connection(test_id)
    else:
        print("\n⚠️ Chưa có file credentials.json")
        print("Vui lòng tạo theo hướng dẫn ở trên")