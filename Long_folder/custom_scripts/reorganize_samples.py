import os
import sys
import shutil

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sample_dir = os.path.join(BASE_DIR, "sample_Long")

input_base = os.path.join(sample_dir, "input")
output_base = os.path.join(sample_dir, "output")

if not os.path.exists(sample_dir):
    print(f"❌ Không tìm thấy thư mục {sample_dir}")
    sys.exit(1)

def organize_folder(base_path, ext):
    if not os.path.exists(base_path):
        return 0
        
    moved_count = 0
    for fname in os.listdir(base_path):
        fpath = os.path.join(base_path, fname)
        if os.path.isfile(fpath) and fname.endswith(ext):
            name_no_ext = fname[:-len(ext)]
            if name_no_ext.isdigit():
                idx = int(name_no_ext)
                part_num = (idx - 1) // 500 + 1
                part_dir = os.path.join(base_path, f"part_{part_num}")
                os.makedirs(part_dir, exist_ok=True)
                
                target_path = os.path.join(part_dir, fname)
                shutil.move(fpath, target_path)
                moved_count += 1
                
    return moved_count

print("🔄 Đang tự động chia các tệp hiện tại trong sample_Long thành các subfolder 500 file/thư mục...")
inp_moved = organize_folder(input_base, ".txt")
out_moved = organize_folder(output_base, ".json")

print(f" ✅ Đã phân chia xong:")
print(f"   - {inp_moved} file .txt trong input")
print(f"   - {out_moved} file .json trong output")
