# Reflection — Lab 19

**GitHub:** DngVinh
**Path đã chạy:** Lite, Windows, Python 3.14.7

---

Với BGE-small, Precision@10 của BM25/Vector/Hybrid là
77,8%/73,2%/78,6%. BM25 mạnh ở exact; Hybrid đạt 100% ở mixed vì RRF kết hợp
bằng chứng từ vựng và ngữ nghĩa. Vector chỉ đạt 24% ở paraphrase, thấp hơn
BM25 33,3%: model tiếng Anh không bảo đảm hiểu diễn đạt tiếng Việt.

Audit cố định: query instruction nâng Vector paraphrase lên 25,3% nhưng
Hybrid tổng thể giảm còn 77,2%. NFC/dấu câu nâng BM25 lên 82,8%, vượt
Hybrid 79,6%. Không cấu hình BGE thử nghiệm nào đạt đủ lát cắt.
MiniLM/ensemble cải thiện paraphrase nhưng thua BM25 trên mixed; giữ riêng
kết quả, không ghép model theo nhãn query.

Tôi chọn BM25 cho mã hoặc thuật ngữ chính xác, độ trễ thấp;
vector đa ngữ cho diễn đạt lại. Hybrid cần hai tín hiệu hữu ích;
RRF đúng không bảo đảm chất lượng thắng.

---

## Điều ngạc nhiên nhất khi làm lab này

Ngưỡng cache 0,75 gây 36% false hit; 0,85 đạt 0% trên tập kiểm chứng này.

---

## Bonus challenge

- [x] Đã làm Bonus: agent dùng Feast và memory hybrid, demo đủ 5 query.
