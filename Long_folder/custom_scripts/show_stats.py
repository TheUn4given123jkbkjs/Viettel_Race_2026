import os
import sys
import json

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def inspect_member_stats(member_name):
    member_dir = os.path.join(BASE_DIR, f"sample_{member_name}")
    if not os.path.exists(member_dir):
        return None
        
    input_dir = os.path.join(member_dir, "input")
    output_dir = os.path.join(member_dir, "output")
    meta_dir = os.path.join(member_dir, "metadata")
    stats_file = os.path.join(member_dir, "stats.json")
    
    # Đếm số lượng file thực tế
    total_txt = 0
    if os.path.exists(input_dir):
        for root, _, files in os.walk(input_dir):
            total_txt += sum(1 for f in files if f.endswith(".txt"))
            
    total_json = 0
    if os.path.exists(output_dir):
        for root, _, files in os.walk(output_dir):
            total_json += sum(1 for f in files if f.endswith(".json"))
            
    by_provider = {}
    by_account = {}
    total_meta = 0
    
    if os.path.exists(meta_dir):
        for root, _, files in os.walk(meta_dir):
            for f in files:
                if f.endswith(".json"):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8") as mf:
                            data = json.load(mf)
                            p = data.get("provider", "UNKNOWN").upper()
                            a = data.get("account", "UNKNOWN").upper()
                            by_provider[p] = by_provider.get(p, 0) + 1
                            by_account[a] = by_account.get(a, 0) + 1
                            total_meta += 1
                    except Exception:
                        pass
                        
    # Đọc stats.json nếu có
    saved_stats = None
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r", encoding="utf-8") as sf:
                saved_stats = json.load(sf)
        except Exception:
            pass
            
    return {
        "member": member_name,
        "total_txt": total_txt,
        "total_json": total_json,
        "total_metadata": total_meta,
        "by_provider": by_provider,
        "by_account": by_account,
        "saved_stats": saved_stats
    }

def main():
    print("=" * 80)
    print("📊 BÁO CÁO THỐNG KÊ DỮ LIỆU SINH HUẤN LUYỆN (DATA GENERATION STATS)")
    print("=" * 80)
    
    members = ["A", "Long", "B", "C"]
    found_any = False
    
    for m in members:
        res = inspect_member_stats(m)
        if not res or (res["total_txt"] == 0 and res["total_json"] == 0):
            continue
            
        found_any = True
        print(f"\n📁 Thư mục: sample_{m}")
        print(f"  • Số file văn bản (.txt):  {res['total_txt']} / 2000 mẫu")
        print(f"  • Số file gán nhãn (.json): {res['total_json']} / 2000 mẫu")
        
        if res["by_provider"]:
            print(f"  • Phân bổ theo Provider (từ metadata):")
            for p, cnt in sorted(res["by_provider"].items()):
                pct = (cnt / res["total_metadata"]) * 100 if res["total_metadata"] > 0 else 0
                print(f"     - [{p:10}]: {cnt:5d} mẫu ({pct:.1f}%)")
                
            if res["by_account"]:
                print(f"  • Phân bổ chi tiết theo Tài khoản (Top Accounts):")
                sorted_accs = sorted(res["by_account"].items(), key=lambda x: x[1], reverse=True)[:5]
                for acc, cnt in sorted_accs:
                    print(f"     - TK [{acc:15}]: {cnt:5d} mẫu")
        else:
            print(f"  • Metadata: Chưa có metadata lưu kèm (các mẫu cũ trước khi cập nhật logger).")
            
        print(f"  • Trạng thái file stats.json: {'✅ Đã lưu' if res['saved_stats'] else '⚙️ Đang tạo mới'}")

    if not found_any:
        print("Chưa tìm thấy thư mục mẫu nào có dữ liệu.")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
