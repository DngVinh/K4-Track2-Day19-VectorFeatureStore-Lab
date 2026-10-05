# Đối chiếu Lab 19 — Core 100 / Advanced 50 / Bonus 20

Đánh giá kỹ thuật ngày 05/10/2026 (Asia/Bangkok), không phải điểm giảng viên.
“Có output” nghĩa là có phép đo thực trong notebook được
[manifest cuối](FINAL_EVIDENCE.json) chọn, mã nguồn khớp và không có error output.
Theo yêu cầu mới của người dùng, PNG render được dùng làm screenshot bài nộp.
Bộ [8 screenshot hiện hành](screenshots/CURRENT_SCREENSHOTS.html) khớp output
cuối: làm lại NB2–NB6, giữ NB1/NB7/NB8 vì nội dung không đổi; bản cũ được giữ.
NB2 vẫn thiếu tiêu chí lát cắt nên không tuyên bố toàn bộ bài đạt 170 điểm.

| Core | Điểm rubric | Trạng thái kỹ thuật / bằng chứng |
|---|---:|---|
| NB1 count lab19 = 1000 | 5 | Có output và assertion |
| NB1 top-5 keyword | 5 | Có 5 hit với score |
| NB1 paraphrase không có cloud | 10 | 5/5 cloud; assertion |
| NB2 RRF 1/(60+rank), rank 1-based | 10 | Mã nguồn + test công thức/union candidates |
| NB2 Hybrid P@10 > cả hai baseline | 10 | BGE 78,6% > BM25 77,8% / Vector 73,2% |
| NB2 người thắng từng lát cắt cùng cấu hình | 5 | **Chưa đạt**: Vector paraphrase 24,0% < BM25 33,3%; BGE mixed Hybrid 100%; exact BM25/Hybrid 96,7% |
| NB3 valid SearchResponse + latency_ms | 5 | Model validation cho response thật qua HTTP |
| NB3 3 modes P50/P95/P99 server-side | 10 | Warmup 10/mode rồi 100 request/mode |
| NB3 Hybrid P99 < 50ms | 10 | Cuối: server-side 27,1 ms, client wall-clock 29,0 ms |
| NB4 apply + list đúng 3 views | 5 | CLI exit 0, có tên cả 3 views |
| NB4 materialize-incremental | 5 | Log materialization + lookup xác minh số entity thật |
| NB4 u_001 online features | 5 | reading_speed=187, affinity=cloud, queries/hour=11 |
| NB4 100 lookup P99 <10ms | 5 | Cuối: 0,65 ms; first lookup 70,15 ms báo riêng; assertion giữ nguyên |
| NB4 PIT 3 hàng × features | 5 | Snapshot 177/184/201; assertion loại snapshot tương lai |
| Tái lập setup-lite && make benchmark | 5 | Bash + Make thật exit 0, 5.000 call/mode, Hybrid P99 23,7 ms; venv và model cache mới |

| Advanced | Điểm rubric | Trạng thái kỹ thuật / bằng chứng |
|---|---:|---|
| NB5 recall theo selectivity | 5 | 3,8%: post-filter 0,00 / filtered retrieval 1,00 |
| NB5 over-fetch ladder | 5 | fetch_k 10/50/200/500: 0,03/0,27/0,80/1,00 |
| NB6 3 chiến lược budget 16, agentic thắng recall/balance | 5 | Assertion ngân sách mỗi query và tổng doc từ trace; bảng 3 chiến lược |
| NB6 giải thích filter thấp hơn no-filter | 4 | Topic suy đoán loại mất tài liệu bên cạnh; notebook §3–§4 |
| NB6 build_context Feast + doc_ids | 3 | Features thật; assertion affinity cloud và doc_ids không rỗng |
| NB7 sweep tiết kiệm + trả lời sai | 5 | 75 positive / 75 negative probes, 7 thresholds |
| NB7 chọn ngưỡng, giải thích 0,75 | 4 | 0,75 false-hit 36%; 0,85 correct reuse 100%, false-hit 0% trên calibration probes |
| NB7 tenant leak / namespace MISS | 3 | Hai trường hợp thật và assertions; dữ liệu demo tổng hợp |
| NB8 target-naive gap >0,30, in-fold ≈0 | 4 | 0,477 và −0,011; assertions |
| NB8 PIT vs latest: % rò + AUC | 4 | 98,2%; AUC 0,715 vs 0,595, delta 0,120 |
| NB8 cùng user 2 amount → 2 ratio | 4 | u_000: 0,03 / 4,21, spike 0/1; assertions |
| make test + make verify-lite môi trường mới | 4 | Cả hai exit 0; 45 passed, không skipped; test không thay thế tiêu chí notebook |

| Bonus | Điểm rubric | Trạng thái kỹ thuật / bằng chứng |
|---|---:|---|
| Architecture ≥600 từ, có sơ đồ | 3 | 991 từ; Mermaid flow từ memory/profile tới LLM adapter |
| 3 quyết định có tradeoff | 6 | Chunking 160/24 word units; bảng vs embedding profile; freshness theo use case |
| Bối cảnh tiếng Việt | 2 | Unicode NFC, âm tiết cách trắng, giữ dấu, code-switching |
| Phương án bị loại có lý do | 2 | Không lưu episodic memory trong một Feast feature; lookup không thay nearest-neighbor |
| remember + recall chạy được | 4 | Qdrant + BM25 + RRF và Feast; test privacy scope cả hai retriever |
| demo exit0, 5 queries | 3 | Log Bonus; 5 context và kiểm tra cross-user / user chưa có memory |

## Kiểm soát tính trung thực và giới hạn

- Corpus/golden nguyên bản và fresh phải khớp SHA-256 trong environment/data_hashes.
  Không sửa nhãn, query hay relevance để đạt điểm.
- NB2 có 4 ablation định trước, không thay model bắt buộc. Ranking chỉ nhận text;
  nhãn đọc sau khi đóng băng rankings. Không chọn depth, k, trọng số theo golden.
  Golden đã biết nên đây là diagnostic, không phải test held-out.
- Query instruction và preprocessing hợp lệ đều chưa giải quyết toàn bộ lát cắt.
  Không chứng minh rubric bất khả thi, chỉ chứng minh các cấu hình đã đo chưa đạt.
  MiniLM/ensemble là bảng riêng và latency API BGE không áp cho chúng.
- Qdrant local mode lọc đúng nhưng không chứng minh tốc độ HNSW production.
  NB6 truth sinh từ exact cosine cho từng sub-question; đây là thí nghiệm tổng hợp,
  không phải bộ nhãn độc lập của người dùng thật.
- Ngưỡng cache 0,85 được chọn trên calibration probes, không có bảo đảm 0% lỗi
  trên query mới. Feast activity demo là batch materialized, chưa có streaming.
- Reflection 198 từ (≤200), Architecture 991 từ (≥600). Không gọi LLM trả phí.
- Không commit/push, đổi Public hay nộp LMS. Public/LMS do người dùng thực hiện.
