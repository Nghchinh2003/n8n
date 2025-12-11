"""
customer_profile_manager.py
Quản lý hồ sơ khách hàng và session mapping (Zalo ID, FB ID, etc.)
"""

import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CustomerProfileManager:
    """
    Quản lý hồ sơ khách hàng với persistent storage.

    Features:
    - Map platform ID (zalo_id, fb_id) → internal session_id
    - Lưu thông tin khách hàng (tên, SĐT, địa chỉ, sở thích)
    - Lưu lịch sử tương tác
    - Persistent storage (JSON file)
    """

    def __init__(self, storage_file: str = "./data/customer_profiles.json"):
        """
        Khởi tạo customer profile manager.

        Args:
            storage_file: File lưu trữ profiles
        """
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(exist_ok=True)

        # profiles[customer_id] = {...thông tin khách...}
        self.profiles: Dict[str, Dict] = {}

        # platform_mapping[platform_id] = customer_id
        # Ví dụ: platform_mapping["zalo:123456"] = "cust_001"
        self.platform_mapping: Dict[str, str] = {}

        self._load_profiles()

        logger.info(f"CustomerProfileManager khởi tạo với {len(self.profiles)} khách hàng")

    def _load_profiles(self):
        """Load profiles từ file."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.profiles = data.get('profiles', {})
                    self.platform_mapping = data.get('platform_mapping', {})
                logger.info(f"Đã load {len(self.profiles)} profiles")
            except Exception as e:
                logger.error(f"Lỗi khi load profiles: {e}")
        else:
            logger.info("Chưa có file profiles, tạo mới")

    def _save_profiles(self):
        """Lưu profiles vào file."""
        try:
            data = {
                'profiles': self.profiles,
                'platform_mapping': self.platform_mapping,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("Đã lưu profiles")
        except Exception as e:
            logger.error(f"Lỗi khi lưu profiles: {e}")

    def get_or_create_customer(
            self,
            platform: str,
            platform_id: str,
            initial_data: Optional[Dict] = None
    ) -> str:
        """
        Lấy hoặc tạo customer ID từ platform ID.

        Args:
            platform: Nền tảng (zalo, facebook, telegram, etc.)
            platform_id: ID trên nền tảng đó
            initial_data: Dữ liệu ban đầu nếu tạo mới

        Returns:
            customer_id (internal ID)
        """
        key = f"{platform}:{platform_id}"

        # Nếu đã có mapping
        if key in self.platform_mapping:
            customer_id = self.platform_mapping[key]
            logger.debug(f"Tìm thấy khách hàng: {customer_id}")
            return customer_id

        # Tạo mới
        customer_id = f"cust_{len(self.profiles) + 1:04d}"

        profile = {
            'customer_id': customer_id,
            'platform': platform,
            'platform_id': platform_id,
            'created_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'info': initial_data or {},
            'preferences': {},
            'interaction_history': []
        }

        self.profiles[customer_id] = profile
        self.platform_mapping[key] = customer_id

        self._save_profiles()

        logger.info(f"Tạo khách hàng mới: {customer_id} ({platform}:{platform_id})")

        return customer_id

    def update_customer_info(
            self,
            customer_id: str,
            info: Dict,
            merge: bool = True
    ):
        """
        Cập nhật thông tin khách hàng.

        Args:
            customer_id: ID khách hàng
            info: Thông tin cần cập nhật
            merge: True = merge với info cũ, False = ghi đè
        """
        if customer_id not in self.profiles:
            logger.warning(f"Không tìm thấy khách hàng: {customer_id}")
            return

        if merge:
            self.profiles[customer_id]['info'].update(info)
        else:
            self.profiles[customer_id]['info'] = info

        self.profiles[customer_id]['last_seen'] = datetime.now().isoformat()

        self._save_profiles()

        logger.info(f"Cập nhật thông tin khách hàng: {customer_id}")

    def add_interaction(
            self,
            customer_id: str,
            interaction_type: str,
            details: Dict
    ):
        """
        Thêm lịch sử tương tác.

        Args:
            customer_id: ID khách hàng
            interaction_type: Loại tương tác (order, inquiry, complaint, etc.)
            details: Chi tiết tương tác
        """
        if customer_id not in self.profiles:
            return

        interaction = {
            'timestamp': datetime.now().isoformat(),
            'type': interaction_type,
            'details': details
        }

        self.profiles[customer_id]['interaction_history'].append(interaction)

        # Giới hạn lịch sử (giữ 50 tương tác gần nhất)
        if len(self.profiles[customer_id]['interaction_history']) > 50:
            self.profiles[customer_id]['interaction_history'] = \
                self.profiles[customer_id]['interaction_history'][-50:]

        self._save_profiles()

    def get_customer_profile(self, customer_id: str) -> Optional[Dict]:
        """
        Lấy profile đầy đủ của khách hàng.

        Args:
            customer_id: ID khách hàng

        Returns:
            Profile dict hoặc None
        """
        return self.profiles.get(customer_id)

    def get_customer_context(self, customer_id: str) -> str:
        """
        Lấy context về khách hàng để đưa vào prompt.

        Args:
            customer_id: ID khách hàng

        Returns:
            Chuỗi text mô tả khách hàng
        """
        profile = self.profiles.get(customer_id)

        if not profile:
            return "Khách hàng mới, chưa có lịch sử."

        context = "THÔNG TIN KHÁCH HÀNG:\n"

        # Thông tin cơ bản
        info = profile.get('info', {})
        if info:
            context += f"- Tên: {info.get('name', 'Chưa có')}\n"
            context += f"- SĐT: {info.get('phone', 'Chưa có')}\n"
            context += f"- Địa chỉ: {info.get('address', 'Chưa có')}\n"

        # Sở thích
        preferences = profile.get('preferences', {})
        if preferences:
            context += f"- Sở thích: {', '.join(preferences.keys())}\n"

        # Lịch sử tương tác gần đây
        history = profile.get('interaction_history', [])
        if history:
            context += f"\nLỊCH SỬ TƯƠNG TÁC GẦN ĐÂY ({len(history[-3:])} lần):\n"
            for interaction in history[-3:]:
                timestamp = interaction['timestamp'][:10]  # Chỉ lấy ngày
                itype = interaction['type']
                context += f"- {timestamp}: {itype}\n"

        return context

    def search_customers(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Tìm kiếm khách hàng theo tên, SĐT, etc.

        Args:
            query: Từ khóa tìm kiếm
            limit: Số kết quả tối đa

        Returns:
            List các profiles phù hợp
        """
        query_lower = query.lower()
        results = []

        for customer_id, profile in self.profiles.items():
            # Tìm trong info
            info_str = json.dumps(profile.get('info', {}), ensure_ascii=False).lower()

            if query_lower in info_str or query_lower in customer_id.lower():
                results.append(profile)

            if len(results) >= limit:
                break

        return results

    def get_stats(self) -> Dict:
        """Lấy thống kê về khách hàng."""
        return {
            'total_customers': len(self.profiles),
            'platforms': list(set(p.split(':')[0] for p in self.platform_mapping.keys())),
            'recent_customers': len([
                p for p in self.profiles.values()
                if (datetime.now() - datetime.fromisoformat(p['last_seen'])).days <= 7
            ])
        }


# ============================================
# HELPER: INTEGRATION VỚI AGENTS
# ============================================

def get_customer_aware_prompt(
        base_prompt: str,
        customer_context: str
) -> str:
    """
    Thêm customer context vào system prompt.

    Args:
        base_prompt: System prompt gốc
        customer_context: Context về khách hàng

    Returns:
        Prompt đã được bổ sung
    """
    return f"""{base_prompt}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{customer_context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LƯU Ý: Sử dụng thông tin trên để cá nhân hóa câu trả lời, gọi tên khách hàng nếu có."""


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    manager = CustomerProfileManager("./data/test_profiles.json")

    # Khách mới từ Zalo
    cust_id = manager.get_or_create_customer("zalo", "123456789")
    print(f"Customer ID: {cust_id}")

    # Cập nhật thông tin
    manager.update_customer_info(cust_id, {
        "name": "Nguyễn Văn A",
        "phone": "0123456789",
        "address": "123 Đường ABC, TP.HCM"
    })

    # Thêm tương tác
    manager.add_interaction(cust_id, "order", {"product": "sơn dầu", "amount": 2})

    # Lấy context
    print("\n" + manager.get_customer_context(cust_id))

    # Lần sau khách quay lại
    cust_id_2 = manager.get_or_create_customer("zalo", "123456789")
    print(f"\nKhách quay lại: {cust_id_2} (same as {cust_id}? {cust_id == cust_id_2})")