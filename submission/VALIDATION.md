# Lab 19 — kết quả kiểm chứng

Ngày kiểm chứng: **05/10/2026**, múi giờ Asia/Bangkok.
Đã chạy **Lite trên Windows, Python 3.14.7**. Docker là lộ trình tùy chọn của
rubric và chưa được chạy; không có kết quả Docker nào được suy diễn từ Lite.

## Audit bổ sung của phiên tiếp tục

Baseline BGE giữ nguyên: BM25/Vector/Hybrid **77,8% / 73,2% / 78,6%**.
NB2 mới ở [run 032016Z](runs/20261005T032016Z_527f26/02_hybrid_search_rrf.ipynb)
khớp mã nguồn hiện tại, giữ assertions và báo rõ **UNMET** cho Vector paraphrase.
Các notebook cũ cùng log lỗi đều được bảo toàn.

| Ablation BGE cố định | BM25 tổng thể | Vector tổng thể | Hybrid tổng thể | Vector paraphrase |
|---|---:|---:|---:|---:|
| Nguyên bản | 77,8% | 73,2% | 78,6% | 24,0% |
| Query instruction | 77,8% | 73,6% | 77,2% | 25,3% |
| NFC + dấu câu BM25 | 82,8% | 73,2% | 79,6% | 24,0% |
| Instruction + NFC | 82,8% | 73,6% | 80,4% | 25,3% |

Bộ thử khai báo cố định trước đánh giá, dùng BGE-small, top-50, RRF k=60,
rank 1-based và mẫu số Precision@10 bằng 10. Ranking chỉ nhận query text;
nhãn được đọc sau khi đã đóng băng ranking. Không dò trọng số, chọn retriever
theo loại query hoặc tự chọn cấu hình từ golden. Đây là diagnostic trên
golden đã biết, không có tuyên bố held-out. [JSON đủ rankings từng query](checks/nb2_fixed_ablations_20261005.json),
[stdout và exit 0 của audit](checks/nb2_audit_20261005T031749Z_9f0a0b.txt).

Theo [model card BGE](https://huggingface.co/BAAI/bge-small-en-v1.5), query
instruction có thể dùng cho retrieval và không thêm vào passages; v1.5 cũng
hỗ trợ không instruction. FastEmbed 0.8.1 đang cài không tự thêm instruction
cho BGE trong `query_embed()`. Thí nghiệm cho thấy thêm instruction không
giải quyết paraphrase tiếng Việt và làm Hybrid tổng thể thấp hơn BM25.
NFC/dấu câu giúp lexical matching nhưng Hybrid không vượt baseline BM25 mới.
Không thay cấu hình bắt buộc; **tiêu chí lát cắt 5 điểm vẫn chưa đạt**.

[Chẩn đoán corpus/tokenizer](checks/corpus_diagnosis_20261005T032729Z_e2c374.txt):
1.000 tài liệu, 10×100 topic, không trùng title+text; 111–159 token/tài liệu,
median 135; không tài liệu nào bị cắt ở 512 token, không có `[UNK]` trong
corpus/query. Mọi relevance set đúng 100 ID của topic. Không phát hiện sai
RRF, mất corpus hoặc sai denominator. Model tiếng Anh xử lý được token nhưng
không bảo đảm ranking ngữ nghĩa tiếng Việt tốt. Đây là giải thích phù hợp
kết quả đo, không phải chứng minh rubric bất khả thi.

Test sau sửa cache mặc định: **45 passed**, exit 0,
[log](checks/tests_cache_final_20261005T032807Z_771091.txt).
Reflection **198 từ**, Architecture **991 từ**. Bảng từng tiêu chí ở
[RUBRIC_REVIEW.md](RUBRIC_REVIEW.md); [FINAL_EVIDENCE.json](FINAL_EVIDENCE.json)
chọn output khớp source, giữ notebook cũ. Checker kiểm tra source/hash và
artifact, không suy ra điểm từ số test pass.

### Sửa quy trình Windows và kiểm soát CPU

- Setup nhận `python3` hoặc `python`, activate `Scripts` hoặc `bin`, truyền
  `sys.executable` thật cho uv, áp dill override cho Python 3.14.
- Cache, Jupyter config/data/runtime và IPython nằm trong workspace; không
  tạo `.jupyter` ở profile hay thay permissions. Jupytext/corpus/advanced
  generators được bỏ qua khi output đã có; cặp corpus/golden thiếu một file
  dừng với thông báo bảo toàn dữ liệu.
- Make dùng `python -m pytest` trên Windows. GNU Make 4.4.1 portable từ
  [MSYS2](https://packages.msys2.org/packages/mingw-w64-x86_64-make), kiểm tra
  SHA-256 gói `c19e7caf09bbc89b2730556b2da73004118d4e1f967a685cc48524c7ff80d864`.
  Không cài hệ thống hoặc chỉnh PATH toàn hệ thống.
- Logger dùng UTF-8 và thư mục temp riêng cho từng check, giữ stdout/stderr
  và exit code. Các phiên lỗi trước đó vẫn còn trong `submission/runs/`.
- Lần benchmark đầy đủ với thread tự động có Hybrid P99 **67,6 ms**, exit 2
  của Make; [stdout](runs/20261005T034821Z_reproduction_dcbce5/setup_benchmark.stdout.txt).
  Không tính lần này là đạt. Logger khi đó cũng lỗi encode console; đã sửa.
- FastEmbed API/benchmark hiện dùng **1 thread ONNX** cố định. Theo
  [ONNX Runtime](https://onnxruntime.ai/docs/performance/tune-performance/threading.html),
  thread mặc định dùng các core vật lý và có spin-wait, có thể gây contention.
  Phép đo chẩn đoán 500 call/mode đạt Hybrid P99 **23,0 ms**, giữ nguyên toàn
  bộ quality/slice; [log](checks/cpu_thread_diagnostic_20261005T035940Z_8fb57a.txt).
  Index corpus mất 109,9 s so với 60,1 s ở lần thread tự động. Đây là đánh đổi
  batch throughput và độ ổn định query, không phải thay ranking/model.
  Hai lần chạy không kiểm soát hoàn toàn tải nền; không khẳng định thread pool
  là nguyên nhân duy nhất. Diagnostic 500 call không thay thế benchmark 5.000.

### Tái lập cuối bằng Bash + GNU Make thật

Run [20261005T040443Z_reproduction_7d5aac](runs/20261005T040443Z_reproduction_7d5aac/)
tạo venv trống mới, không sao chép `.venv`, model cache, `.git`, credential
hoặc dữ liệu sinh sẵn. Python/UV là công cụ đã có. Wheel đã tải bằng môi trường
kiểm chứng mới trong **chính phiên này** được uv dùng lại để cài dependency;
nguồn ghi ở [copy_manifest.json](runs/20261005T040443Z_reproduction_7d5aac/copy_manifest.json).
Không gọi đây là lần download dependency hoàn toàn không cache. BGE tải lại
vào model cache mới; corpus/golden/advanced data được sinh mới, không dựa
vào dữ liệu hay môi trường Lab của phiên trước.

| Lệnh literal | Kết quả cuối | Bằng chứng |
|---|---|---|
| `bash setup-lite.sh && make benchmark` | **exit 0**, 5.000 call/mode; Hybrid 78,6% > 77,8%/73,2% | [stdout](runs/20261005T040443Z_reproduction_7d5aac/setup_benchmark.stdout.txt), [stderr](runs/20261005T040443Z_reproduction_7d5aac/setup_benchmark.stderr.txt), [exit/time/command](runs/20261005T040443Z_reproduction_7d5aac/setup_benchmark.json) |
| `make test` | **exit 0**, **45 passed**, không skipped | [stdout](runs/20261005T040443Z_reproduction_7d5aac/make_test.stdout.txt), [record](runs/20261005T040443Z_reproduction_7d5aac/make_test.json) |
| `make verify-lite` | **exit 0**, All checks passed | [stdout](runs/20261005T040443Z_reproduction_7d5aac/make_verify_lite.stdout.txt), [record](runs/20261005T040443Z_reproduction_7d5aac/make_verify_lite.json) |

| Searcher benchmark cuối (5.000 call/mode) | P50 | P95 | P99 |
|---|---:|---:|---:|
| keyword | 1,3 ms | 1,8 ms | 2,0 ms |
| semantic | 13,9 ms | 18,3 ms | 20,7 ms |
| hybrid | 16,2 ms | 21,2 ms | **23,7 ms < 50 ms** |

Đây là timer quanh `Searcher.search`, không phải wall-clock HTTP.
NB3 đo riêng `latency_ms` trong endpoint. Các mode vẫn chạy đủ 50 query ×100,
10 warmup/mode, không bỏ call chậm, không thay k/depth/metric.
Python 3.14.7, uv 0.12.23, Bash 5.3.9, GNU Make 4.4.1;
[version record](runs/20261005T040443Z_reproduction_7d5aac/tools.stdout.txt),
[dependency versions](runs/20261005T040443Z_reproduction_7d5aac/environment.stdout.txt).
[Data hashes](runs/20261005T040443Z_reproduction_7d5aac/data_hashes.json) khớp bản gốc.

### Notebook và Bonus sau sửa cuối

NB2 được chạy lại riêng; NB3/4/5/6/8 được chạy lại trong môi trường mới ở trên,
đều **exit 0**. NB1/NB7 không đổi nên giữ output đã kiểm chứng. Toàn bộ code
**và Markdown** của 8 notebook được [manifest](FINAL_EVIDENCE.json) chọn khớp
source hiện tại. App, Bonus, notebook, setup, benchmark, test và dependency
files khớp SHA-256 snapshot đã chạy; chỉ README và hai script chuẩn bị/kiểm
tra artifact được cập nhật sau snapshot, không thay kết quả runtime.

| Kiểm chứng cuối | Kết quả | Output gốc |
|---|---|---|
| NB3 HTTP thật, 10 warmup + 100 request/mode | P99 server-side keyword **2,9**, semantic **19,3**, hybrid **27,1 ms**; hybrid client wall-clock **29,0 ms** | [NB3](runs/20261005T040443Z_reproduction_7d5aac/notebooks/20261005T041234Z_30d889/03_search_api_benchmark.txt) |
| NB4 Feast | 3 views, 100/1.000/100 entity; PIT 177/184/201; 100 lookup P50 **0,42**, P95 **0,54**, P99 **0,65 ms** | [NB4](runs/20261005T040443Z_reproduction_7d5aac/notebooks/20261005T041234Z_30d889/04_feast_feature_store.txt) |
| NB5 | Selectivity 3,8%: recall post-filter **0,00** / filtered **1,00**; over-fetch 500 đạt **1,00** | [NB5](runs/20261005T040443Z_reproduction_7d5aac/notebooks/20261005T041234Z_30d889/05_filtered_search.txt) |
| NB6 | Budget 16; recall single/no-filter/filter **0,526 / 0,922 / 0,839**, balance **0,08 / 0,92 / 0,75**; reflection và Feast context đạt | [NB6](runs/20261005T040443Z_reproduction_7d5aac/notebooks/20261005T041234Z_30d889/06_agent_retrieval.txt) |
| NB8 | Gap **0,477 / −0,011**; latest leak **98,2%**, AUC **0,715 / 0,595**; cùng user ratios **0,03 / 4,21** | [NB8](runs/20261005T040443Z_reproduction_7d5aac/notebooks/20261005T041234Z_30d889/08_feature_engineering.txt) |
| Bonus | **exit 0**, đủ 5 context; cross-user isolation và user chưa có memory đạt | [stdout](runs/20261005T040443Z_reproduction_7d5aac/bonus.stdout.txt), [record](runs/20261005T040443Z_reproduction_7d5aac/bonus.json) |

NB4 lần lookup đầu **70,15 ms**, được in riêng trước benchmark 100 call;
không gộp cold-start vào P99 steady-state và không tuyên bố cold-start <10 ms.
Setup + benchmark, notebook và Bonus đều có command/time/exit trong
[results.json](runs/20261005T040443Z_reproduction_7d5aac/results.json).

Artifact checker xác minh execution counts, không error, source/hash, bảo toàn
8 notebook cũ qua capture manifest và giới hạn số từ: **exit 0**,
[log cuối](checks/submission_final_fulltext_20261005T042725Z_3df916.txt).
**Cập nhật screenshot theo yêu cầu mới của người dùng:** ảnh render được
chấp nhận làm screenshot bài nộp. Đã làm lại **NB2–NB6** từ output cuối;
NB1/NB7/NB8 giữ nguyên vì output hiển thị giống hoàn toàn. Bộ hiện hành **8/8**
ở [mục lục](screenshots/CURRENT_SCREENSHOTS.html), nguồn notebook, SHA-256 ảnh
và fingerprint nội dung ở [manifest](screenshots/CURRENT_SCREENSHOTS.json).
Không còn yêu cầu người dùng chụp thủ công. Phương pháp vẫn ghi chính xác là
render output đã thực thi, không đổi provenance thành browser capture.

Trước khi người dùng chấp nhận cách này, check riêng cửa sổ trả exit 1:
[log lịch sử](checks/screenshots_pending_20261005T042546Z_19e6f5.txt), được giữ.
Checker hiện xác minh đủ 8 ảnh theo manifest, PNG hashes và nội dung khớp
notebook cuối; thay đổi này chỉ áp dụng artifact, không nới tiêu chí NB2.
`check_submission.py --require-screenshots` **exit 0**, đủ **8/8**;
[log cuối](checks/screenshots_current_20261005T044137Z_9c6d81.txt).

## Kết quả phiên trước — giữ để đối chiếu

| Tiêu chí | Bằng chứng thực đo |
|---|---|
| NB1: corpus/index | 1.000 văn bản, 1.000 ID duy nhất, 10 chủ đề × 100; Qdrant 384 chiều COSINE, batch 64 |
| NB1: top-5 | In đủ 5 kết quả có score; query paraphrase không chứa `cloud` trả **5/5 cloud** |
| NB2: RRF | `1/(60+rank)`, rank bắt đầu từ 1, top-50 mỗi retriever; có regression test công thức |
| NB2: chất lượng tổng thể, BGE-small | BM25 **77,8%**, Vector **73,2%**, Hybrid **78,6%** trên đủ 50 query |
| NB2: lát cắt | Giữ các bảng theo model bên dưới; không thay corpus, query hoặc ground truth để đạt điểm |
| NB3: API | `/healthz` ready với 1.000 docs; response `/search` được kiểm tra bằng `SearchResponse.model_validate` |
| NB3: latency | 10 warmup/mode bị loại khỏi thống kê, 50 query × 2 lượt = 100 request/mode; Hybrid server-side P99 **20,5 ms < 50 ms** |
| NB4: Feast | `apply` và `feature-views list` thành công; đúng 3 views, materialize vào SQLite |
| NB4: số entity online | Lookup thật xác nhận **100 user profile, 1.000 item popularity, 100 query velocity**; item IDs khớp corpus |
| NB4: lookup | `u_001`: reading speed 187, language vi, affinity cloud, queries/hour 11, distinct topics 4 |
| NB4: latency | 100 lookup: P50 **0,44 ms**, P95 **0,69 ms**, P99 **0,79 ms < 10 ms** |
| NB4: PIT | 3 hàng; tốc độ đọc **177/184/201** khớp snapshot tại hoặc trước event; hai snapshot khác nhau kiểm chứng việc loại giá trị tương lai |
| Test suite | **45 passed**, exit 0; [log](checks/tests_20261005T024756Z_65aa3f.txt) |
| Smoke test | `All checks passed`, exit 0; [log](checks/smoke_20261005T023629Z_3e719e.txt) |
| Benchmark đầy đủ | 5.000 call/mode, Hybrid P99 **22,2 ms**, quality thắng cả hai baseline, exit 0; [log](checks/benchmark_20261005T024338Z_af2933.txt) |

### Precision@10 theo loại query

**BGE-small Lite bắt buộc — API và benchmark latency dùng model này.**

| Query | n | BM25 | Vector | Hybrid |
|---|---:|---:|---:|---:|
| exact | 15 | 96,7% | 88,7% | 96,7% |
| paraphrase | 15 | 33,3% | 24,0% | 32,0% |
| mixed | 20 | 97,0% | 98,5% | **100,0%** |

**MiniLM đa ngữ — thí nghiệm riêng**, cùng corpus, query, BM25, RRF k=60
và top-50. Precision tổng thể: BM25 77,8%, Vector 75,8%, Hybrid **80,6%**.

| Query | n | BM25 | Vector | Hybrid |
|---|---:|---:|---:|---:|
| exact | 15 | 96,7% | 90,0% | 98,0% |
| paraphrase | 15 | 33,3% | **48,0%** | 44,0% |
| mixed | 20 | **97,0%** | 86,0% | 95,0% |

**Ensemble cố định 50/50**, ghép hai vector đã chuẩn hóa thành 768 chiều,
không học trọng số từ golden set. Precision tổng thể: BM25 77,8%, Vector
78,0%, Hybrid **81,2%**. Tái sử dụng vector corpus, không embed lại.

| Query | n | BM25 | Vector | Hybrid |
|---|---:|---:|---:|---:|
| exact | 15 | 96,7% | 93,3% | 98,0% |
| paraphrase | 15 | 33,3% | **49,3%** | 44,7% |
| mixed | 20 | **97,0%** | 88,0% | 96,0% |

**Giới hạn cần đọc khi đối chiếu rubric:** BGE-small không thắng paraphrase;
MiniLM và ensemble cải thiện paraphrase nhưng Hybrid của chúng không thắng
BM25 trên mixed. BGE Hybrid thắng mixed. Không một cấu hình đo ở đây thỏa
đồng thời mọi kỳ vọng người thắng theo lát cắt. Các bảng được báo cáo riêng,
không chọn model theo nhãn query và không trộn số liệu để tuyên bố đạt toàn bộ
kỳ vọng trong một cấu hình. Điểm cuối cùng do giảng viên đánh giá bằng bằng
chứng này. Latency API dùng **BGE**, không áp cho các model thí nghiệm.

### API latency server-side

| Mode | P50 | P95 | P99 |
|---|---:|---:|---:|
| keyword | 1,4 ms | 2,2 ms | 2,3 ms |
| semantic | 12,8 ms | 14,9 ms | 17,6 ms |
| hybrid | 14,9 ms | 18,5 ms | **20,5 ms** |

Là thời gian xử lý search được endpoint báo trong `latency_ms`, không gồm
network hoặc serialization response. Client wall-clock được in riêng trong NB3.
P99 dùng cách lấy phần tử `int(n * 0.99)` sau khi sắp xếp, theo mẫu lab.

## Advanced Missions — output phiên trước

| Mission | Kết quả |
|---|---|
| NB5: filtered search | Filter 3,8%: post-filter recall **0,00**, filtered retrieval **1,00**; cả ba tenant đạt recall 1,00 với filter trong truy vấn |
| NB5: over-fetch | Recall trung bình 0,03/0,27/0,80/**1,00** với fetch_k 10/50/200/**500**; cần 50% corpus |
| NB6: cùng ngân sách | Mỗi planner được cấp đúng **16 document**; kiểm tra tổng document trả về từ các call không vượt ngân sách |
| NB6: chất lượng | Single-shot recall **0,526**, balance **0,08**; agentic không filter **0,922/0,92**; agentic có filter **0,839/0,75** |
| NB6: reflection/context | Filter quá chặt trả 0; retry nới filter trả 8; `build_context` có Feast affinity `cloud`, language `vi` và doc IDs thật |
| NB7: calibration | Threshold 0,75: cold false-hit **36%**; 0,85: correct reuse **100%**, cold false-hit **0%**, positive wrong-answer **0%** |
| NB7: TTL/tenant | Expiry tạo MISS; không namespace làm lộ dữ liệu ACME cho GLOBEX, namespace tạo MISS; có assertions và tests |
| NB8: 6 họ feature | Window counts, ratios, lag/delta, recency, categorical encoding, embedding matrix 3×384 được thực thi |
| NB8: leakage | Session target-naive gap **0,477 > 0,30**, in-fold **−0,011**; fold prior lấy từ các fold khác |
| NB8: PIT vs latest | Latest join rò **98,2%** hàng, AUC **0,715**; PIT AUC **0,595**; chênh **0,120** |
| NB8: ODFV | Cùng `u_000`, baseline 3.566.076: amount 100.000 → ratio **0,03**, amount 15.000.000 → **4,21**; spike 0/1 |

Qdrant local mode kiểm chứng **recall đúng**, không kiểm chứng tốc độ HNSW
production; payload index không được dùng trong local mode. NB7 dùng dữ liệu
tổng hợp và đồng hồ ảo. Threshold 0,85 chỉ được hiệu chỉnh trên tập probe này,
không phải bảo đảm false-hit bằng 0 trên dữ liệu mới.

## Bonus và bộ bài nộp

- [ARCHITECTURE.md](../bonus/ARCHITECTURE.md): **991 từ**, sơ đồ Mermaid,
  ba quyết định với đánh đổi, phương án bị loại, bối cảnh tiếng Việt và giới hạn.
- [agent.py](../bonus/agent.py): `remember`/`recall`, Qdrant + BM25 + RRF,
  user filter ở cả hai ranker, profile/activity thật từ Feast.
- [demo.py](../bonus/demo.py): đủ **5 query**, exit 0; kiểm tra memory user khác
  không xuất hiện và user chưa có memory trả rỗng. Output cuối nằm trong bảng
  trên; [output phiên trước](bonus_demo.txt) được giữ.
- 8 notebook `.ipynb` có đầy đủ execution counts và không có error output,
  chọn theo [FINAL_EVIDENCE.json](FINAL_EVIDENCE.json); notebook cũ ở
  [notebooks](../notebooks/) được giữ nguyên.
- [REFLECTION.md](REFLECTION.md): **198 từ** tính cả tiêu đề và metadata.
- [environment.json](environment.json): version, hash corpus/golden set,
  immutable revision của hai model đã kiểm tra kích thước và SHA-256.
- [Bộ screenshot hiện hành](screenshots/CURRENT_SCREENSHOTS.html): 8 PNG khớp
  output cuối, có hash trong [CURRENT_SCREENSHOTS.json](screenshots/CURRENT_SCREENSHOTS.json).
  5 ảnh mới ở `screenshots/final-20261005/`; 3 ảnh cũ còn khớp được dùng lại.
- 8 PNG/HTML và [capture manifest cũ](screenshots/capture_manifest.json) được
  giữ nguyên làm lịch sử; NB2–NB6 cũ không thuộc bộ bài nộp hiện hành.
- [HTML toàn bộ output](screenshots/manual-20261005/index.html) và
  [hướng dẫn chụp trực tiếp](screenshots/MANUAL_CAPTURE.md) vẫn có để tùy chọn xem/chụp.

**PNG render từ stdout notebook được người dùng chấp nhận làm screenshot.**
Không có tuyên bố đã chụp bằng browser. Giới hạn Chrome/Edge/UI của phiên trước
vẫn ghi trong log; không tắt sandbox hay thay chính sách bảo vệ. Đầy đủ output
gốc được giữ. Ảnh mới được kiểm tra trực quan, không cắt dòng cuối hoặc bảng.
Ảnh API hiển thị 3/10 hits để dễ đọc; JSON đủ 10 hits nằm trong NB3. Ảnh NB4
rút gọn protobuf diff dài, giữ dòng apply/update và bảng ba views.

## Chạy lại trên Windows

```powershell
.\.venv\Scripts\python.exe scripts/portable_make.py
.\.venv\Scripts\python.exe -X utf8 scripts/verify_reproduction.py --notebooks
.\.venv\Scripts\python.exe scripts/check_submission.py
```

Chạy trong workspace gốc với Git Bash và Python có sẵn. Wrapper tạo thư mục
con mới, venv/cache/data mới, chạy literal ba lệnh Make, notebook và Bonus;
stdout/stderr/exit code ở run riêng. Default không dùng lại package cache.
Lệnh chính xác của lượt đo cuối chỉ rerun notebook bị ảnh hưởng và dùng lại
wheel tải trong chính phiên kiểm chứng này:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/verify_reproduction.py --notebooks --notebook-numbers 03 04 05 06 08 --package-cache .cache/reproduction/20261005T031901Z_reproduction_932328/.cache/uv
```

`check_submission.py` kiểm tra bộ evidence đã chốt trong manifest; mỗi lượt
reproduction mới có manifest/log riêng, không tự ghi đè evidence đã chốt.
Kiểm tra bộ screenshot đã chốt, không cần chụp thêm:

```powershell
.\.venv\Scripts\python.exe scripts/check_submission.py --require-screenshots
```

Checker đối chiếu nội dung render input với notebook cuối và hash ảnh.
Người chấm vẫn có thể xem ảnh từ mục lục. Runner dùng
kernel đúng interpreter `.venv`, giữ notebook có sẵn; output mới luôn ở
`submission/runs/`. NB3 dùng cổng local
còn trống và chỉ dừng process do nó tạo. Notebook Feast dùng CLI module
`python -m feast.cli.cli` với interpreter đang chạy, không cần launcher exe.

Không chạy lại `capture_evidence.py` vào thư mục ảnh hiện có: script cũ có thể
ghi đè render trước. `refresh_screenshots.py` tạo ảnh mới riêng và chỉ chạy
một lần cho bộ hiện hành; nếu cần lượt cập nhật khác, dùng đích mới để giữ lịch sử.
NB4/NB8 sinh/materialize dữ liệu, nên để bảo toàn môi trường gốc hãy dùng
`scripts/verify_reproduction.py --notebooks` cho lần chạy mới.

Windows pin **PyArrow 24.0.0**: version 25 bị Application Control chặn DLL
Parquet; version 24 hoạt động. Python 3.14 dùng override **dill 0.4.1**.
Không thay Windows security policy. Các registry, data và log cũ được giữ,
bao gồm lần chạy lỗi trước khi sửa môi trường, để có thể kiểm tra lịch sử.

Đã chuẩn bị bài trong workspace; screenshot đã đủ theo thỏa thuận người dùng,
NB2 lát cắt vẫn là khoảng thiếu được nêu ở audit. **Chưa commit/push, chưa đổi quyền Public,
chưa nộp VinUni LMS.** Không tự thực hiện các thao tác xuất bản từ tài liệu
tham khảo; repository cá nhân dùng remote `DngVinh/K4-Track2-Day19-VectorFeatureStore-Lab`.
