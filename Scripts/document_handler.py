import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentHandler:

    def __init__(self, documents_dir: str = "./documents"):
        """
        Khởi tạo document handler.

        Args:
            documents_dir: Thư mục chứa TẤT CẢ tài liệu sản phẩm
        """
        self.documents_dir = Path(documents_dir)
        self.documents_dir.mkdir(exist_ok=True)

        # Cache: documents[filename] = {metadata, content}
        self.documents: Dict[str, Dict] = {}

        # Cache sản phẩm riêng (nếu có file JSON/CSV)
        self.products_cache: Dict[str, Dict] = {}

        logger.info(f"DocumentHandler khởi tạo với thư mục: {documents_dir}")

    def load_all_documents(self, recursive: bool = True):

        logger.info(f"Đang quét tài liệu trong {self.documents_dir}...")

        # Xóa cache cũ
        self.documents.clear()
        self.products_cache.clear()

        # Quét files
        if recursive:
            file_paths = list(self.documents_dir.rglob("*"))
        else:
            file_paths = list(self.documents_dir.glob("*"))

        # Chỉ lấy files (không phải folder)
        file_paths = [f for f in file_paths if f.is_file()]

        logger.info(f"Tìm thấy {len(file_paths)} files")

        for file_path in file_paths:
            try:
                ext = file_path.suffix.lower()

                if ext == '.txt':
                    self._load_txt(file_path)
                elif ext == '.json':
                    self._load_json(file_path)
                elif ext == '.csv':
                    self._load_csv(file_path)
                elif ext == '.pdf':
                    self._load_pdf(file_path)
                else:
                    logger.debug(f"Bỏ qua file {file_path.name} (extension không hỗ trợ)")

            except Exception as e:
                logger.error(f"Lỗi khi load {file_path.name}: {e}")

        logger.info(f" Đã load {len(self.documents)} tài liệu và {len(self.products_cache)} sản phẩm")
        self._print_summary()

    def _print_summary(self):
        """In ra summary các tài liệu đã load."""
        if self.documents:
            logger.info("\n Danh sách tài liệu:")
            for doc_name in sorted(self.documents.keys()):
                doc = self.documents[doc_name]
                content_len = len(doc.get('content', ''))
                logger.info(f"  - {doc_name} ({doc['type']}, {content_len} ký tự)")

    def _load_txt(self, file_path: Path):
        """Load file TXT - Ví dụ: thông tin sơn 2K, hướng dẫn sử dụng."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Lưu vào documents với metadata
        self.documents[file_path.stem] = {
            'filename': file_path.name,
            'filepath': str(file_path),
            'type': 'text',
            'content': content,
            'size': len(content)
        }

        logger.debug(f" TXT: {file_path.name} ({len(content)} ký tự)")

    def _load_json(self, file_path: Path):
        """Load file JSON - Ví dụ: danh sách sản phẩm, bảng giá."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Lưu raw JSON vào documents
        content_str = json.dumps(data, ensure_ascii=False, indent=2)
        self.documents[file_path.stem] = {
            'filename': file_path.name,
            'filepath': str(file_path),
            'type': 'json',
            'content': content_str,
            'data': data,
            'size': len(content_str)
        }

        # Nếu là danh sách sản phẩm, lưu vào products_cache
        if isinstance(data, list):
            for item in data:
                if 'id' in item or 'name' in item:
                    key = item.get('id', item.get('name'))
                    self.products_cache[key] = item
        elif isinstance(data, dict):
            if 'products' in data:
                for item in data['products']:
                    key = item.get('id', item.get('name'))
                    self.products_cache[key] = item

        logger.debug(f" JSON: {file_path.name}")

    def _load_csv(self, file_path: Path):
        """Load file CSV - Ví dụ: bảng thông số kỹ thuật sơn."""
        import csv

        rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))

                # Nếu có cột 'id' hoặc 'name', lưu vào products
                if 'id' in row or 'name' in row:
                    key = row.get('id', row.get('name'))
                    self.products_cache[key] = dict(row)

        # Lưu vào documents
        content_str = json.dumps(rows, ensure_ascii=False, indent=2)
        self.documents[file_path.stem] = {
            'filename': file_path.name,
            'filepath': str(file_path),
            'type': 'csv',
            'content': content_str,
            'data': rows,
            'size': len(rows)
        }

        logger.debug(f" CSV: {file_path.name} ({len(rows)} rows)")

    def _load_pdf(self, file_path: Path):
        """Load file PDF - Ví dụ: tài liệu kỹ thuật chi tiết."""
        try:
            import PyPDF2

            text = ""
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(pdf_reader.pages):
                    text += f"\n--- Trang {page_num + 1} ---\n"
                    text += page.extract_text() + "\n"

            self.documents[file_path.stem] = {
                'filename': file_path.name,
                'filepath': str(file_path),
                'type': 'pdf',
                'content': text,
                'pages': len(pdf_reader.pages),
                'size': len(text)
            }

            logger.debug(f" PDF: {file_path.name} ({len(pdf_reader.pages)} trang)")

        except ImportError:
            logger.warning(f"⚠ PyPDF2 chưa cài, bỏ qua {file_path.name}")
        except Exception as e:
            logger.error(f" Lỗi đọc PDF {file_path.name}: {e}")

    def search_in_documents(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Tìm kiếm thông tin trong TẤT CẢ tài liệu.

        Args:
            query: Từ khóa tìm kiếm (ví dụ: "sơn 2k", "thông số kỹ thuật")
            limit: Số kết quả tối đa

        Returns:
            List các document snippets chứa thông tin liên quan
        """
        query_lower = query.lower()
        results = []

        for doc_name, doc_data in self.documents.items():
            content = doc_data.get('content', '')
            content_lower = content.lower()

            # Tìm vị trí xuất hiện
            if query_lower in content_lower:
                # Lấy đoạn text xung quanh (context)
                index = content_lower.find(query_lower)
                start = max(0, index - 200)
                end = min(len(content), index + 200)
                snippet = content[start:end]

                results.append({
                    'document': doc_name,
                    'filename': doc_data['filename'],
                    'type': doc_data['type'],
                    'snippet': snippet.strip(),
                    'relevance': content_lower.count(query_lower)
                })

        # Sắp xếp theo relevance
        results.sort(key=lambda x: x['relevance'], reverse=True)

        return results[:limit]

    def search_products(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Tìm kiếm sản phẩm (từ JSON/CSV).

        Args:
            query: Từ khóa tìm kiếm
            limit: Số kết quả tối đa

        Returns:
            List các sản phẩm phù hợp
        """
        query_lower = query.lower()
        results = []

        for product_id, product_data in self.products_cache.items():
            text_to_search = json.dumps(product_data, ensure_ascii=False).lower()

            if query_lower in text_to_search:
                results.append({
                    'id': product_id,
                    **product_data
                })

            if len(results) >= limit:
                break

        return results

    def get_relevant_context(self, query: str, max_length: int = 2000) -> str:
        """
        Lấy context liên quan từ TẤT CẢ tài liệu để đưa vào prompt.

        Args:
            query: Câu hỏi/từ khóa của user
            max_length: Độ dài tối đa của context

        Returns:
            Chuỗi text chứa thông tin liên quan
        """
        # Tìm kiếm trong documents
        doc_results = self.search_in_documents(query, limit=3)

        # Tìm kiếm trong products
        product_results = self.search_products(query, limit=3)

        context = ""

        # Thêm thông tin từ documents
        if doc_results:
            context += "THÔNG TIN TỪ TÀI LIỆU:\n\n"
            for result in doc_results:
                context += f"[{result['filename']}]\n{result['snippet']}\n\n"

        # Thêm thông tin sản phẩm
        if product_results:
            context += "THÔNG TIN SẢN PHẨM:\n\n"
            for product in product_results:
                context += f"- {product.get('name', product.get('id'))}:\n"
                for key, value in product.items():
                    if key not in ['id', 'name']:
                        context += f"  {key}: {value}\n"
                context += "\n"

        # Cắt ngắn nếu quá dài
        if len(context) > max_length:
            context = context[:max_length] + "..."

        return context if context else "Không tìm thấy thông tin liên quan trong tài liệu."

    def list_all_documents(self) -> List[str]:
        """Lấy danh sách tất cả tài liệu đã load."""
        return list(self.documents.keys())

    def get_document(self, doc_name: str) -> Optional[Dict]:
        """Lấy nội dung đầy đủ của 1 tài liệu."""
        return self.documents.get(doc_name)


# ============================================
# HELPER: TẠO CẤU TRÚC FOLDER MẪU
# ============================================

def create_sample_documents_structure():
    """Tạo cấu trúc folder mẫu với nhiều file."""

    base_dir = Path("./documents")
    base_dir.mkdir(exist_ok=True)

    # 1. File: Thông tin sơn 2K
    with open(base_dir / "thong_tin_son_2k.txt", "w", encoding="utf-8") as f:
        f.write("""THÔNG TIN SƠN 2K (SƠN HAI THÀNH PHẦN)

1. ĐẶC ĐIỂM:
- Sơn 2K là sơn 2 thành phần: Base (sơn chính) + Hardener (chất đóng rắn)
- Độ cứng cao, chống xước tốt
- Độ bóng cao, màu sắc đẹp
- Thời gian khô: 2-4 giờ

2. ỨNG DỤNG:
- Sơn xe máy, ô tô
- Sơn kim loại cao cấp
- Sơn đồ gỗ nội thất

3. CÁCH PHA CHẾ:
- Tỷ lệ pha: Base : Hardener = 2:1
- Thêm dung môi nếu cần (tối đa 10%)
- Khuấy đều trước khi sơn

4. BẢO QUẢN:
- Nơi khô ráo, thoáng mát
- Tránh ánh nắng trực tiếp
- Sau khi mở nắp, sử dụng trong 6 tháng

5. GIÁ THAM KHẢO:
- Sơn 2K trắng: 200,000đ/kg
- Sơn 2K màu: 250,000đ/kg
""")

    # 2. File: Thông tin sơn 1K
    with open(base_dir / "thong_tin_son_1k.txt", "w", encoding="utf-8") as f:
        f.write("""THÔNG TIN SƠN 1K (SƠN MỘT THÀNH PHẦN)

1. ĐẶC ĐIỂM:
- Sơn 1 thành phần, sẵn sàng sử dụng
- Dễ thi công, phù hợp thợ phổ thông
- Giá thành rẻ hơn sơn 2K
- Thời gian khô: 4-6 giờ

2. ỨNG DỤNG:
- Sơn tường nhà
- Sơn đồ gỗ thông thường
- Sơn kim loại công nghiệp

3. CÁCH PHA CHẾ:
- Có thể sử dụng trực tiếp
- Pha loãng với dung môi nếu cần (tỷ lệ 1:0.2)

4. GIÁ THAM KHẢO:
- Sơn 1K trắng: 120,000đ/kg
- Sơn 1K màu: 150,000đ/kg
""")

    # 3. File: Bảng thông số kỹ thuật (CSV)
    import csv
    with open(base_dir / "bang_thong_so_ky_thuat.csv", "w", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Loại sơn', 'Độ bóng', 'Thời gian khô (giờ)', 'Độ bền (năm)', 'Độ che phủ (m²/kg)',
                         'Nhiệt độ thi công (°C)'])
        writer.writerow(['Sơn 2K', 'Cao (90%)', '2-4', '7-10', '10-12', '15-35'])
        writer.writerow(['Sơn 1K', 'Trung bình (60%)', '4-6', '3-5', '8-10', '15-35'])
        writer.writerow(['Sơn nước', 'Thấp (30%)', '2-3', '3-5', '12-15', '10-40'])
        writer.writerow(['Sơn dầu', 'Cao (85%)', '6-8', '5-7', '8-10', '15-35'])

    # 4. File: Danh sách sản phẩm (JSON)
    products = {
        "products": [
            {
                "id": "son-2k-trang",
                "name": "Sơn 2K Trắng",
                "type": "Sơn 2 thành phần",
                "color": "Trắng",
                "weights": ["1kg", "5kg"],
                "price": {"1kg": 200000, "5kg": 950000},
                "description": "Sơn 2K cao cấp, độ bóng cao"
            },
            {
                "id": "son-1k-do",
                "name": "Sơn 1K Đỏ",
                "type": "Sơn 1 thành phần",
                "color": "Đỏ",
                "weights": ["1kg", "3kg"],
                "price": {"1kg": 150000, "3kg": 420000},
                "description": "Sơn 1K màu đỏ tươi, dễ thi công"
            }
        ]
    }

    with open(base_dir / "danh_sach_san_pham.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # 5. File: Hướng dẫn thi công
    with open(base_dir / "huong_dan_thi_cong.txt", "w", encoding="utf-8") as f:
        f.write("""HƯỚNG DẪN THI CÔNG SƠN

A. CHUẨN BỊ BỀ MẶT:
1. Làm sạch bề mặt
2. Chà nhám bằng giấy nhám P180-P240
3. Lau sạch bụi

B. PHA SƠN:
- Sơn 2K: Base + Hardener (2:1) + Dung môi (nếu cần)
- Sơn 1K: Pha loãng với dung môi 10-20%

C. THI CÔNG:
1. Sơn lót (nếu cần): 1 lớp
2. Chờ khô 4-6 giờ
3. Chà nhám nhẹ
4. Sơn phủ: 2-3 lớp, mỗi lớp cách 2-4 giờ

D. BẢO DƯỠNG:
- Không rửa trong 7 ngày đầu
- Tránh va đập mạnh
""")

    logger.info(f" Đã tạo cấu trúc folder mẫu trong {base_dir}")
    logger.info("   - thong_tin_son_2k.txt")
    logger.info("   - thong_tin_son_1k.txt")
    logger.info("   - bang_thong_so_ky_thuat.csv")
    logger.info("   - danh_sach_san_pham.json")
    logger.info("   - huong_dan_thi_cong.txt")


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)

    # Tạo files mẫu
    create_sample_documents_structure()

    # Load và test
    handler = DocumentHandler("./documents")
    handler.load_all_documents()

    print("\n" + "=" * 60)
    print("TEST TÌM KIẾM")
    print("=" * 60)

    # Test 1: Tìm thông tin về sơn 2K
    print("\n1. Tìm kiếm 'sơn 2k':")
    context = handler.get_relevant_context("sơn 2k")
    print(context[:500] + "...")

    # Test 2: Tìm bảng thông số
    print("\n2. Tìm kiếm 'thông số kỹ thuật':")
    context = handler.get_relevant_context("thông số kỹ thuật")
    print(context[:500] + "...")

    # Test 3: Tìm sản phẩm
    print("\n3. Tìm sản phẩm 'sơn trắng':")
    products = handler.search_products("trắng")
    for p in products:
        print(f"- {p['name']}: {p.get('price', 'N/A')}")