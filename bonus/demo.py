"""Five required queries. Run NB4 first, then python bonus/demo.py."""
from agent import HybridMemoryAgent


def main():
    agent = HybridMemoryAgent()
    for memory in [
        "Tôi đã đọc tài liệu Kubernetes Pod lifecycle, triển khai container và autoscaling.",
        "Tôi lưu hướng dẫn tự động mở rộng hạ tầng theo lưu lượng, giảm chi phí cloud bằng spot instance.",
        "Cloud security: mã hóa dữ liệu, TLS, zero-trust và xác thực OAuth hai yếu tố.",
        "Tôi tìm hiểu quản lý mạng VPC và cân bằng tải multi-region.",
        "Ghi chú hôm nay: tôi quan tâm cloud, thích ví dụ tiếng Việt ngắn gọn.",
    ]:
        agent.remember(memory)
    agent.remember("PRIVATE_OTHER_USER: thông tin riêng của người dùng khác", "u_002")
    queries = ["Tôi đã đọc gì về Kubernetes?", "Recommend đọc gì tiếp",
               "Tôi đang quan tâm gì gần đây?", "Tài liệu về tự động mở rộng hạ tầng?",
               "Cho tôi summary cloud security"]
    for i, query in enumerate(queries, 1):
        context = agent.recall(query)
        assert "PRIVATE_OTHER_USER" not in context
        print(f"\nQUERY {i}/5\n{context}")
    assert agent.retrieve("Kubernetes", "unknown_user") == []
    print("\nPASS — five contexts assembled; cross-user memory isolation verified")


if __name__ == "__main__":
    main()
