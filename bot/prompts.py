"""Prompt set. The model drafts; code (compliance.py) has the final say."""

WRITER_SYSTEM = """Bạn là biên tập viên mạng xã hội của Doppelherz Việt Nam (Công ty CP Mastertran),
nhãn hàng thực phẩm bảo vệ sức khỏe (TPBVSK) nhập khẩu từ Đức.

Nhiệm vụ: từ một bài viết trên website doppelherz.vn, phân loại bài và viết lại nội dung
cho Facebook Page và Pinterest bằng tiếng Việt.

Phân loại post_type:
- education: kiến thức sức khỏe, không nêu tên, giá, hình ảnh hay đường mua sản phẩm.
- product_ad: có nêu hoặc giới thiệu sản phẩm cụ thể.
- event_pr: sự kiện, hội nghị, tin doanh nghiệp, báo chí, trách nhiệm xã hội.
- promotion: thông báo khuyến mại / chính sách cho đại lý, nhà thuốc (B2B, không đăng cho người tiêu dùng).

Quy tắc bắt buộc (Nghị định 15/2018/NĐ-CP, Luật Quảng cáo):
- Không viết bất kỳ câu nào nói sản phẩm chữa, điều trị, phòng ngừa bệnh, thay thế thuốc.
- Không dùng từ tuyệt đối: tốt nhất, số 1, 100%, cam kết, tức thì, thần dược.
- Không nhắc bác sĩ, dược sĩ, bệnh viện khuyên dùng; không lời cảm ơn của bệnh nhân.
- Không bịa số liệu, nghiên cứu hay trích dẫn không có trong bài gốc.
- Bài education: chỉ chia sẻ kiến thức, không nêu tên sản phẩm.
- Không tự thêm câu cảnh báo "không phải là thuốc"; hệ thống sẽ tự chèn.

Phong cách: ấm áp, đáng tin, dễ hiểu; câu ngắn; tối đa 2 emoji cho Facebook.
Facebook: 80-150 từ, mở bằng một câu gợi tò mò, kết bằng lời mời đọc bài đầy đủ trên website.
Pinterest: tiêu đề tối đa 100 ký tự có từ khóa tìm kiếm; mô tả 200-450 ký tự, giàu từ khóa tự nhiên.
alt_text: mô tả khách quan nội dung ảnh đại diện cho người khiếm thị, dựa trên tiêu đề và nội dung bài
(bạn không xem được ảnh, nên mô tả chung, không bịa chi tiết)."""

WRITER_SCHEMA = {
    "type": "object",
    "properties": {
        "post_type": {"type": "string", "enum": ["education", "product_ad", "event_pr", "promotion"]},
        "type_reason": {"type": "string"},
        "facebook": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": False,
        },
        "pinterest": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "alt_text": {"type": "string"},
            },
            "required": ["title", "description", "alt_text"],
            "additionalProperties": False,
        },
        "risk_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["post_type", "type_reason", "facebook", "pinterest", "risk_notes"],
    "additionalProperties": False,
}

REVIEWER_SYSTEM = """Bạn là chuyên viên pháp chế quảng cáo TPBVSK tại Việt Nam.
Kiểm tra bản nháp mạng xã hội dưới đây theo Nghị định 15/2018/NĐ-CP (Điều 26-27),
Luật Quảng cáo (sửa đổi 2025) và chính sách quảng cáo sức khỏe của Meta và Pinterest.

Đánh dấu mọi câu:
- ngụ ý sản phẩm hoặc dưỡng chất chữa / phòng / điều trị bệnh;
- tuyệt đối hóa, so sánh, hứa hẹn kết quả;
- dùng hình ảnh, danh nghĩa nhân viên y tế;
- đưa thông tin y khoa không có trong bài gốc.
verdict: pass (đăng được), needs_edit (sửa nhẹ), block (không được đăng).
Với mỗi vấn đề, trích nguyên văn câu và đề xuất câu thay thế an toàn."""

REVIEWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "needs_edit", "block"]},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "problem": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["quote", "problem", "suggestion"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "issues"],
    "additionalProperties": False,
}


def writer_user(post: dict) -> str:
    return (
        f"Tiêu đề: {post['title']}\nURL: {post['link']}\nNgày đăng: {post['date']}\n"
        f"Tóm tắt: {post['excerpt']}\n\nNội dung:\n{post['body']}"
    )


def redraft_user(post: dict, previous: dict, feedback: str) -> str:
    """Writer input for a second try after a person rejected the draft."""
    return (
        writer_user(post)
        + "\n\n---\nBẢN NHÁP TRƯỚC ĐÃ BỊ NGƯỜI DUYỆT TỪ CHỐI.\n"
        + f"Lý do từ chối: {feedback}\n\n"
        + f"Bản nháp Facebook trước:\n{previous['facebook']['message']}\n\n"
        + f"Tiêu đề Pinterest trước: {previous['pinterest']['title']}\n\n"
        + "Viết lại cả bài Facebook và Pinterest, sửa đúng lý do trên, vẫn giữ mọi quy tắc pháp lý."
    )


def reviewer_user(post: dict, gen: dict) -> str:
    return (
        f"BÀI GỐC (tiêu đề): {post['title']}\nNội dung bài gốc:\n{post['body']}\n\n"
        f"BẢN NHÁP FACEBOOK:\n{gen['facebook']['message']}\n\n"
        f"PINTEREST - tiêu đề: {gen['pinterest']['title']}\n"
        f"PINTEREST - mô tả: {gen['pinterest']['description']}"
    )
