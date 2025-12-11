from typing import Dict, List
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Quản lý memory cho cuộc hội thoại của từng session và agent.
    Cấu trúc:
        memory[session_id][agent_type] = [messages]
    Điều này giúp tránh trộn lẫn context giữa các agents khác nhau.
    """

    def __init__(self):
        """Khởi tạo bộ nhớ lưu trữ rỗng."""
        # Cấu trúc: memory[session_id] = {'phanloai': [...], 'create_order': [...], 'consulting': [...]}
        self.memory: Dict[str, Dict[str, List[Dict]]] = {}
        logger.info("Memory Manager đã được khởi tạo")

    def _ensure_session(self, session_id: str):
        """Đảm bảo session tồn tại với tất cả agent types đã được khởi tạo."""
        if session_id not in self.memory:
            self.memory[session_id] = {
                'phanloai': [],
                'create_order': [],
                'consulting': []
            }
            logger.debug(f"Đã tạo session mới: {session_id}")

    def get_history(self, session_id: str, agent: str = 'consulting') -> List[Dict]:
        """
        Lấy lịch sử hội thoại cho session và agent cụ thể.
        """
        if not session_id:
            return []

        self._ensure_session(session_id)

        history = self.memory[session_id].get(agent, [])
        logger.debug(f"Đã lấy {len(history)} messages cho session {session_id}, agent {agent}")

        return history

    def add_message(self, session_id: str, agent: str, role: str, content: str):
        """
        Thêm message vào lịch sử của agent cụ thể.
        """
        if not session_id:
            logger.warning("Cố gắng thêm message nhưng không có session_id")
            return

        self._ensure_session(session_id)

        # Tạo message entry
        entry = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        }

        # Thêm vào lịch sử của agent
        self.memory[session_id][agent].append(entry)

        # Giới hạn độ dài lịch sử
        if len(self.memory[session_id][agent]) > Config.MAX_CONVERSATION_HISTORY:
            # Chỉ giữ lại các messages gần đây
            self.memory[session_id][agent] = \
                self.memory[session_id][agent][-Config.MAX_CONVERSATION_HISTORY:]
            logger.debug(f"Đã cắt ngắn lịch sử cho session {session_id}, agent {agent}")

        logger.debug(f"Đã thêm {role} message vào session {session_id}, agent {agent}")

    def clear_session(self, session_id: str, agent: str = None) -> bool:
        """
        Xóa lịch sử của session hoặc agent cụ thể.
        """
        if session_id not in self.memory:
            logger.warning(f"Cố gắng xóa session không tồn tại: {session_id}")
            return False

        if agent:
            # Xóa lịch sử của agent cụ thể
            if agent in self.memory[session_id]:
                self.memory[session_id][agent] = []
                logger.info(f"Đã xóa lịch sử {agent} cho session {session_id}")
                return True
            else:
                logger.warning(f"Không tìm thấy agent {agent} trong session {session_id}")
                return False
        else:
            # Xóa toàn bộ session
            del self.memory[session_id]
            logger.info(f"Đã xóa tất cả lịch sử cho session {session_id}")
            return True

    def get_active_sessions(self) -> int:
        """
        Đếm số sessions đang hoạt động.
        Returns:Số lượng sessions đang hoạt động
        """
        return len(self.memory)

    def get_session_info(self, session_id: str) -> Dict:
        """
        Lấy thông tin tổng quan về session.
        Args: session_id: ID định danh session
        Returns: Dict chứa thống kê session
        """
        if session_id not in self.memory:
            return {
                'exists': False,
                'session_id': session_id
            }

        info = {
            'exists': True,
            'session_id': session_id,
            'agents': {}
        }

        for agent_type, messages in self.memory[session_id].items():
            info['agents'][agent_type] = {
                'message_count': len(messages),
                'last_message': messages[-1]['timestamp'] if messages else None
            }

        return info

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """
        Xóa các sessions không hoạt động trong thời gian dài.
        Args: max_age_hours: Thời gian tối đa tính bằng giờ trước khi cleanup
        """
        from datetime import timedelta

        current_time = datetime.now()
        sessions_to_delete = []

        for session_id, agents in self.memory.items():
            # Tìm message gần nhất trong tất cả agents
            most_recent = None

            for agent_messages in agents.values():
                if agent_messages:
                    last_msg_time = datetime.fromisoformat(agent_messages[-1]['timestamp'])
                    if most_recent is None or last_msg_time > most_recent:
                        most_recent = last_msg_time

            # Kiểm tra nếu session đã cũ
            if most_recent and (current_time - most_recent) > timedelta(hours=max_age_hours):
                sessions_to_delete.append(session_id)

        # Xóa các sessions cũ
        for session_id in sessions_to_delete:
            del self.memory[session_id]
            logger.info(f"Đã dọn dẹp session cũ: {session_id}")

        if sessions_to_delete:
            logger.info(f"Đã dọn dẹp {len(sessions_to_delete)} sessions cũ")

        return len(sessions_to_delete)