# Doppelherz Content Bot

Hệ thống đồng bộ nội dung từ website doppelherz.vn sang Facebook Page và Pinterest, có kiểm tra luật quảng cáo thực phẩm bảo vệ sức khỏe và bước người duyệt. Đây là bản chạy thử cho bài test vị trí Quản lý dự án AI Claude.

**Trang demo:** xem hàng đợi duyệt, bản xem trước Facebook và Pinterest, kết quả kiểm tra tuân thủ, yêu cầu API và lịch đăng tại GitHub Pages của repo này.

## Hệ thống làm gì

```
WordPress REST --> Claude viết --> luật trong code + Claude pháp chế --> người duyệt --> Facebook / Pinterest --> báo cáo
```

1. Đọc bài mới và danh sách sản phẩm qua REST API công khai của doppelherz.vn.
2. Claude phân loại bài (kiến thức, quảng cáo sản phẩm, sự kiện, khuyến mại B2B) và viết bài Facebook, tiêu đề và mô tả Pinterest, alt text.
3. Code kiểm tra theo Nghị định 15/2018/NĐ-CP:
   - chặn từ cấm như "chữa", "điều trị", "100%", "tốt nhất";
   - bài có tên sản phẩm được xếp là quảng cáo, tự chèn nhãn "Thực phẩm bảo vệ sức khỏe" và câu cảnh báo, và bị chặn nếu chưa có số xác nhận nội dung quảng cáo;
   - thêm dòng "Nội dung có sự hỗ trợ của AI".
4. Claude đọc lại bản nháp cùng bài gốc như một chuyên viên pháp chế, trích câu rủi ro và đề xuất câu thay.
5. Người duyệt bấm duyệt hoặc từ chối. Không bài nào được đăng nếu chưa duyệt.
6. Bài đã duyệt được lên lịch: Facebook qua Graph API v26.0 (`scheduled_publish_time`), Pinterest qua API v5 (`POST /v5/pins`).
7. Ảnh pin 1000 × 1500 được làm từ ảnh gốc của bài, không dùng AI tạo ảnh.

Bản chạy thử dừng ở bước dựng yêu cầu API (dry run). Đăng thật cần Page token của Facebook và quyền Standard của Pinterest.

## Chạy

```bash
uv venv .venv && uv pip install --python .venv/bin/python anthropic pillow pytest
.venv/bin/python run.py generate     # đọc bài, gọi Claude, kiểm tra luật, làm ảnh pin
.venv/bin/python run.py review       # duyệt trong terminal
.venv/bin/python run.py schedule     # dựng yêu cầu Facebook và Pinterest (dry run)
.venv/bin/python site/build.py       # dựng trang demo site/index.html
.venv/bin/python -m pytest -q tests  # kiểm thử luật, ảnh và lịch
```

Claude được gọi qua Claude Code CLI (`claude -p`) khi không có khóa API, hoặc qua Anthropic SDK khi có `ANTHROPIC_API_KEY`. Đổi mô hình bằng biến `BOT_MODEL`.

## Cấu trúc

| Tệp | Vai trò |
|---|---|
| `bot/wp.py` | Đọc bài và sản phẩm từ WordPress/WooCommerce |
| `bot/prompts.py` | Bộ prompt: biên tập viên và chuyên viên pháp chế |
| `bot/llm.py` | Gọi Claude, trả JSON đúng schema |
| `bot/compliance.py` | Luật quảng cáo TPBVSK chạy trong code |
| `bot/images.py` | Ảnh pin 2:3 có tiêu đề |
| `bot/publish.py` | Lịch đăng và yêu cầu API Facebook, Pinterest |
| `run.py` | Dòng lệnh điều phối |
| `site/` | Trang demo tĩnh |

## Giới hạn

- Thư viện số xác nhận nội dung quảng cáo đang trống, nên mọi bài quảng cáo sản phẩm đều bị chặn. Khi triển khai thật, thư viện lấy từ hồ sơ xác nhận của Mastertran.
- Code chỉ kiểm tra chữ. Ảnh gốc có thể chứa tuyên bố như "Số 1 tại Đức", nên người duyệt vẫn phải xem ảnh.
- Thời gian làm tay 40 phút mỗi bài trên trang demo là giả định, chưa đo tại doanh nghiệp.
- Giới hạn ký tự của Pinterest (tiêu đề 100, mô tả 500) lấy từ tài liệu bên thứ ba, cần đối chiếu tài liệu chính thức.
