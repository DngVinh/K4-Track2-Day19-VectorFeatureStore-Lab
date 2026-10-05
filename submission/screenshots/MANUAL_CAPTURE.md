# Screenshot trực tiếp — thao tác còn lại

**Cập nhật 05/10/2026:** người dùng đã chấp nhận ảnh render làm screenshot.
Không còn bước chụp thủ công bắt buộc. Dùng [bộ screenshot hiện hành](CURRENT_SCREENSHOTS.html)
và [manifest](CURRENT_SCREENSHOTS.json): NB2–NB6 đã làm lại từ output cuối;
NB1/NB7/NB8 giữ nguyên vì output hiển thị giống hoàn toàn. Phần dưới ghi lại
giới hạn UI và hướng dẫn tùy chọn của phiên trước, không phải blocker hiện tại.

Công cụ UI ngày 05/10/2026 trả `apps: []`, `browsers: []`;
`cua.createBrowserTab('iab', 'about:blank')` báo `Browser is not available: iab`.
Native computer APIs cũng bị disabled trong phiên này. Vì vậy agent không
có bề mặt UI để chụp. Không thay sandbox, Application Control hay chính sách
Windows. Các PNG có sẵn là output render, không gọi chúng là screenshot cửa sổ.

1. Mở [trang mục lục](manual-20261005/index.html) bằng Chrome/Edge trên máy.
   Trang dẫn tới output notebook cuối cùng; mỗi trang ghi đường dẫn và SHA-256.
   Cũng có thể mở notebook được chọn trong [FINAL_EVIDENCE.json](../FINAL_EVIDENCE.json)
   bằng Jupyter và chụp trực tiếp cell output.
2. Chọn phần trong menu của từng trang và dùng **Win+Shift+S** để chụp cửa sổ
   hoặc vùng output. Giữ tiêu đề notebook và bảng đọc được, không cắt dòng cuối.
   Lưu ảnh mới tại `submission/screenshots/nb1_window.png` … `nb8_window.png`.
   Nếu nhiều tiêu chí không vừa một ảnh, chụp thêm với hậu tố `_2`, `_3`.
3. Đối chiếu các phần cần thấy dưới đây. Giữ nguyên PNG render và notebook/log cũ.

Sau khi lưu đủ ảnh, có thể kiểm tra file bằng
`.\.venv\Scripts\python.exe scripts/check_submission.py --require-screenshots`.
Checker chỉ kiểm tra sự hiện diện/kích thước ảnh; người chấm vẫn cần xem
ảnh chụp thật, tính đọc được và nội dung đúng tiêu chí.

| Notebook | Output cần chụp |
|---|---|
| NB1 | Indexed 1000, top-5 keyword, top-5 paraphrase thuộc cloud |
| NB2 | Precision tổng thể và bảng exact/paraphrase/mixed BGE; trạng thái paraphrase chưa đạt. Bảng đa ngữ/audit là thí nghiệm riêng |
| NB3 | Response có latency_ms và bảng server-side P50/P95/P99 sau warmup |
| NB4 | apply + danh sách 3 views, materialization, lookup u_001/P99 và PIT 3 hàng |
| NB5 | Recall theo selectivity và ladder fetch_k đạt 1,00 ở 500/1000 docs |
| NB6 | Bảng 3 chiến lược cùng budget 16 và context chứa Feast features/doc_ids |
| NB7 | Sweep tiết kiệm/trả lời sai, threshold đã chọn; leak và MISS theo namespace |
| NB8 | Leakage gap, latest vs PIT (% rò/AUC), cùng user hai amount → hai ratio |

Việc chụp trực tiếp này hiện là tùy chọn; bộ ảnh render đã được người dùng chấp nhận.
Push, đổi Public và nộp LMS là ba thao tác xuất bản riêng, chưa được agent thực hiện.
