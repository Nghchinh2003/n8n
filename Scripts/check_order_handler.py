"""
check_order_handler.py
Xử lý tra cứu đơn hàng từ Google Sheets / Excel
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class OrderDataHandler:
    """
    Xử lý tra cứu đơn hàng từ Google Sheets hoặc Excel.

    Hỗ trợ:
    - Đọc từ Google Sheets (qua API)
    - Đọc từ Excel/CSV local
    - Tìm kiếm đơn hàng theo mã, SĐT, tên
    - Cache để tránh đọc liên tục
    """

    def __init__(
            self,
            data_source: str = "local",  # "local" hoặc "google_sheets"
            local_file: str = "./data/orders.csv",
            sheet_id: Optional[str] = None,
            credentials_file: Optional[str] = None
    ):
        """
        Khởi tạo order data handler.

        Args:
            data_source: Nguồn dữ liệu ("local" hoặc "google_sheets")
            local_file: Đường dẫn file local (CSV/Excel)
            sheet_id: Google Sheets ID (nếu dùng Google Sheets)
            credentials_file: File credentials cho Google Sheets API
        """
        self.data_source = data_source
        self.local_file = local_file
        self.sheet_id = sheet_id
        self.credentials_file = credentials_file

        # Cache orders DataFrame
        self.orders_df: Optional[pd.DataFrame] = None
        self.last_load_time: Optional[datetime] = None
        self.cache_duration = 300  # 5 phút

        logger.info(f"OrderDataHandler khởi tạo với data_source: {data_source}")

    def load_orders(self, force_reload: bool = False):
        """
        Load orders từ nguồn dữ liệu.

        Args:
            force_reload: Bắt buộc reload bỏ qua cache
        """
        # Check cache
        if not force_reload and self.orders_df is not None and self.last_load_time:
            elapsed = (datetime.now() - self.last_load_time).total_seconds()
            if elapsed < self.cache_duration:
                logger.debug("Sử dụng cached orders")
                return

        logger.info(f"Đang load orders từ {self.data_source}...")

        if self.data_source == "local":
            self._load_from_local()
        elif self.data_source == "google_sheets":
            self._load_from_google_sheets()
        else:
            raise ValueError(f"Data source không hợp lệ: {self.data_source}")

        self.last_load_time = datetime.now()
        logger.info(f"Đã load {len(self.orders_df)} đơn hàng")

    def _load_from_local(self):
        """Load orders từ file local (CSV/Excel)."""
        try:
            file_path = self.local_file

            if not os.path.exists(file_path):
                logger.warning(f"File không tồn tại: {file_path}, tạo file mẫu")
                self._create_sample_orders_file(file_path)

            # Đọc file
            if file_path.endswith('.csv'):
                self.orders_df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                self.orders_df = pd.read_excel(file_path)
            else:
                raise ValueError("File phải là .csv, .xlsx hoặc .xls")

            logger.debug(f"Đã load {len(self.orders_df)} rows từ {file_path}")

        except Exception as e:
            logger.error(f"Lỗi khi load từ local: {e}")
            self.orders_df = pd.DataFrame()

    def _load_from_google_sheets(self):
        """Load orders từ Google Sheets."""
        try:
            from google.oauth2.service_account import Credentials
            import gspread

            if not self.sheet_id or not self.credentials_file:
                raise ValueError("Cần sheet_id và credentials_file cho Google Sheets")

            # Authenticate
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]

            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=scopes
            )

            client = gspread.authorize(creds)

            # Open sheet
            sheet = client.open_by_key(self.sheet_id)
            worksheet = sheet.get_worksheet(0)  # Sheet đầu tiên

            # Get all data
            data = worksheet.get_all_records()
            self.orders_df = pd.DataFrame(data)

            logger.debug(f"Đã load {len(self.orders_df)} rows từ Google Sheets")

        except ImportError:
            logger.error("Cần cài gspread và google-auth: pip install gspread google-auth")
            self.orders_df = pd.DataFrame()
        except Exception as e:
            logger.error(f"Lỗi khi load từ Google Sheets: {e}")
            self.orders_df = pd.DataFrame()

    def _create_sample_orders_file(self, file_path: str):
        """Tạo file orders mẫu."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        sample_data = [
            {
                "order_code": "20241129-N-789",
                "customer_name": "Nguyễn Văn A",
                "phone": "0123456789",
                "address": "123 Đường ABC, Quận 1, TP.HCM",
                "product": "Sơn dầu trắng 111 3kg",
                "quantity": 2,
                "total": 800000,
                "status": "Đang giao hàng",
                "created_at": "2024-11-29 10:00:00",
                "updated_at": "2024-11-29 14:00:00"
            },
            {
                "order_code": "20241128-T-456",
                "customer_name": "Trần Thị B",
                "phone": "0987654321",
                "address": "456 Đường XYZ, Quận 2, TP.HCM",
                "product": "Sơn nước xanh 5kg",
                "quantity": 1,
                "total": 300000,
                "status": "Đã giao hàng",
                "created_at": "2024-11-28 09:00:00",
                "updated_at": "2024-11-28 16:00:00"
            }
        ]

        df = pd.DataFrame(sample_data)
        df.to_csv(file_path, index=False, encoding='utf-8')

        logger.info(f"Đã tạo file orders mẫu: {file_path}")

    def search_orders(
            self,
            order_code: Optional[str] = None,
            phone: Optional[str] = None,
            customer_name: Optional[str] = None,
            limit: int = 10
    ) -> List[Dict]:
        """
        Tìm kiếm đơn hàng.

        Args:
            order_code: Mã đơn hàng
            phone: Số điện thoại
            customer_name: Tên khách hàng
            limit: Số kết quả tối đa

        Returns:
            List các đơn hàng phù hợp
        """
        self.load_orders()  # Auto load nếu cần

        if self.orders_df is None or len(self.orders_df) == 0:
            return []

        # Filter
        filtered = self.orders_df.copy()

        if order_code:
            filtered = filtered[
                filtered['order_code'].str.contains(order_code, case=False, na=False)
            ]

        if phone:
            # Loại bỏ khoảng trắng và dấu gạch
            phone_clean = phone.replace(' ', '').replace('-', '')
            filtered = filtered[
                filtered['phone'].astype(str).str.replace(' ', '').str.replace('-', '').str.contains(phone_clean,
                                                                                                     na=False)
            ]

        if customer_name:
            filtered = filtered[
                filtered['customer_name'].str.contains(customer_name, case=False, na=False)
            ]

        # Convert to list of dicts
        results = filtered.head(limit).to_dict('records')

        return results

    def get_order_by_code(self, order_code: str) -> Optional[Dict]:
        """
        Lấy đơn hàng theo mã.

        Args:
            order_code: Mã đơn hàng

        Returns:
            Thông tin đơn hàng hoặc None
        """
        results = self.search_orders(order_code=order_code, limit=1)
        return results[0] if results else None

    def format_order_info(self, order: Dict) -> str:
        """
        Format thông tin đơn hàng thành text dễ đọc.

        Args:
            order: Dict chứa thông tin đơn hàng

        Returns:
            Chuỗi text đã format
        """
        text = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 THÔNG TIN ĐƠN HÀNG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔖 Mã đơn: {order.get('order_code', 'N/A')}
👤 Khách hàng: {order.get('customer_name', 'N/A')}
📞 Số điện thoại: {order.get('phone', 'N/A')}
📍 Địa chỉ: {order.get('address', 'N/A')}

📦 Sản phẩm: {order.get('product', 'N/A')}
🔢 Số lượng: {order.get('quantity', 'N/A')}
💰 Tổng tiền: {order.get('total', 'N/A'):,} VNĐ

📊 Trạng thái: {order.get('status', 'N/A')}
📅 Ngày đặt: {order.get('created_at', 'N/A')}
🔄 Cập nhật: {order.get('updated_at', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return text.strip()

    def get_stats(self) -> Dict:
        """Lấy thống kê đơn hàng."""
        self.load_orders()

        if self.orders_df is None or len(self.orders_df) == 0:
            return {"total_orders": 0}

        stats = {
            "total_orders": len(self.orders_df),
            "status_breakdown": self.orders_df[
                'status'].value_counts().to_dict() if 'status' in self.orders_df.columns else {},
            "total_revenue": self.orders_df['total'].sum() if 'total' in self.orders_df.columns else 0
        }

        return stats


# ============================================
# CHECK ORDER AGENT PROMPT
# ============================================

CHECK_ORDER_PROMPT = """Bạn là nhân viên chăm sóc khách hàng của Sơn Đức Dương, chuyên tra cứu đơn hàng.

NHIỆM VỤ:
1. Nhận thông tin tra cứu từ khách (mã đơn, SĐT, hoặc tên)
2. Tìm kiếm đơn hàng trong hệ thống
3. Cung cấp thông tin chi tiết và rõ ràng
4. Giải đáp thắc mắc về trạng thái đơn hàng

QUY TRÌNH:
- Nếu khách cung cấp mã đơn → Tra cứu trực tiếp
- Nếu khách cung cấp SĐT/tên → Hỏi rõ hơn nếu có nhiều đơn
- Nếu không tìm thấy → Kiểm tra lại thông tin và hướng dẫn liên hệ

PHONG CÁCH:
- Lịch sự, chuyên nghiệp
- Thông tin chính xác, rõ ràng
- Thấu hiểu nếu khách lo lắng về đơn hàng"""

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    handler = OrderDataHandler(data_source="local")
    handler.load_orders()

    print("\n=== Tìm theo mã đơn ===")
    order = handler.get_order_by_code("20241129-N-789")
    if order:
        print(handler.format_order_info(order))

    print("\n=== Tìm theo SĐT ===")
    orders = handler.search_orders(phone="0123456789")
    print(f"Tìm thấy {len(orders)} đơn hàng")

    print("\n=== Thống kê ===")
    print(json.dumps(handler.get_stats(), indent=2, ensure_ascii=False))