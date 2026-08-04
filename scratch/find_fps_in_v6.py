import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

QWEN_DIR = "D:/AI Race/Viettel_Race_2026/finetune_qwen_7b/submission_v6_repaired"
json_files = glob.glob(f"{QWEN_DIR}/*.json")

potential_fps = []

# Keywords that are highly likely to indicate a false positive entity
FP_EXACT = {
    "men", "men g6pd", "đậu tằm", "long não", "băng phiến", "di truyền", 
    "bệnh di truyền lặn", "không có cải thiện", "không cải thiện", "chưa cải thiện",
    "bình thường", "tiền sử bệnh", "bệnh sử", "nhập viện", "xuất viện",
    "hôm nay", "ngày hôm nay", "tuần tới", "sau đó", "ở nhà", "bác sĩ",
    "bệnh nhân", "người bệnh", "phòng khám", "bệnh viện", "khoa cấp cứu",
    "vận động", "gắng sức", "luyện tập", "thể dục", "công việc", "căng thẳng"
}

FP_CONTAINS = [
    r"^ngày\s+\d+",
    r"^lúc\s+\d+",
    r"^\d+\s+ngày",
    r"^\d+\s+tháng",
    r"^\d+\s+năm",
    r"^vs\d+",
    r"\d{5}\s+\d+", # vital signs pattern like 12987 56 18
]

for fpath in json_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
        for ent in data:
            text = ent.get("text", "").strip()
            text_clean = text.lower()
            etype = ent.get("type", "")
            
            is_fp = False
            if text_clean in FP_EXACT:
                is_fp = True
            else:
                for pat in FP_CONTAINS:
                    if re.search(pat, text_clean):
                        is_fp = True
                        break
            
            if is_fp:
                potential_fps.append((fname, text, etype))

print("="*60)
print(f"Potential False Positives found: {len(potential_fps)}")
print("="*60)
for fname, text, etype in potential_fps[:40]:
    print(f"  {fname:10}: '{text}' ({etype})")
print("="*60)
