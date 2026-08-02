import os
import json
import re
import sys
from pathlib import Path

# Setup UTF-8 encoding for console printing on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Import our custom pipeline modules
from ensemble_merger import merge_entities
from hybrid_linker import HybridLinker

try:
    import torch
    from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# Resolve paths relative to this script's location (pipeline/ -> project root)
BASE_DIR = Path(__file__).parent.parent
DEFAULT_INPUT_DIR = BASE_DIR / "test" / "input"
DEFAULT_OUTPUT_DIR = BASE_DIR / "test" / "output"

class EndToEndPipeline:
    def __init__(self, llm_model_path=None, phobert_model_path=None, use_semantic_linker=False):
        print("=" * 80)
        print("  KHỞI TẠO PIPELINE Y KHOA END-TO-END (NER + ASSERTIONS + LINKING)")
        print("=" * 80)
        
        self.device = 0 if (HAS_TORCH and torch.cuda.is_available()) else -1
        print(f"Device cấu hình: {'GPU (cuda:0)' if self.device == 0 else 'CPU'}")
        
        # 1. Initialize Hybrid Linker (Database normalizer)
        self.linker = HybridLinker(use_semantic=use_semantic_linker)
        
        # 2. Load Models (with safety check/mocking if paths not provided yet)
        self.llm_model_path = llm_model_path
        self.phobert_model_path = phobert_model_path
        
        self.load_models()

    def load_models(self):
        # Initialize LLM Pipeline (Placeholder for Qwen2.5-7B LoRA merged model)
        if self.llm_model_path and HAS_TORCH:
            print(f"Đang tải LLM model từ: {self.llm_model_path}...")
            # We use pipeline for text generation
            self.llm_pipeline = pipeline(
                "text-generation",
                model=self.llm_model_path,
                tokenizer=self.llm_model_path,
                device=self.device,
                torch_dtype=torch.float16 if self.device == 0 else torch.float32
            )
        else:
            print("⚠️ LLM model path chưa được cấu hình. Chạy ở chế độ MOCK LLM (Cần cập nhật đường dẫn sau khi train xong).")
            self.llm_pipeline = None

        # Initialize PhoBERT Token Classification Pipeline (Placeholder for PhoBERT-base NER)
        if self.phobert_model_path and HAS_TORCH:
            print(f"Đang tải PhoBERT NER model từ: {self.phobert_model_path}...")
            self.phobert_tokenizer = AutoTokenizer.from_pretrained(self.phobert_model_path, use_fast=False)
            self.phobert_model = AutoModelForTokenClassification.from_pretrained(self.phobert_model_path)
            self.phobert_pipeline = pipeline(
                "ner",
                model=self.phobert_model,
                tokenizer=self.phobert_tokenizer,
                device=self.device,
                aggregation_strategy="simple" # Automatically groups subwords B-X and I-X
            )
        else:
            print("⚠️ PhoBERT model path chưa được cấu hình. Chạy ở chế độ MOCK PhoBERT.")
            self.phobert_pipeline = None

    def run_llm_inference(self, text):
        """
        Calls LLM to extract entities in JSON format (NER + Assertions).
        """
        if not self.llm_pipeline:
            # Mock LLM return for development testing
            return [
                {"text": "tăng huyết áp", "position": [14, 27], "type": "CHẨN_ĐOÁN", "assertions": ["isHistorical"]},
                {"text": "Aspirin", "position": [40, 47], "type": "THUỐC", "assertions": []}
            ]
            
        prompt = f"""Bạn là một chuyên gia y tế AI. Hãy phân tích đoạn văn bản lâm sàng tiếng Việt sau đây, trích xuất tất cả các thực thể y tế và trả về dưới dạng một danh sách JSON.

Với mỗi thực thể, bạn cần xác định:
1. `text`: Đoạn văn bản chính xác của thực thể.
2. `position`: Vị trí ký tự bắt đầu và kết thúc [start, end] trong văn bản gốc.
3. `type`: Nhãn thực thể, nhận một trong các giá trị: TRIỆU_CHỨNG, TÊN_XÉT_NGHIỆM, KẾT_QUẢ_XÉT_NGHIỆM, CHẨN_ĐOÁN, THUỐC.
4. `assertions`: Mảng các thuộc tính ngữ cảnh (chỉ dành cho TRIỆU_CHỨNG, CHẨN_ĐOÁN, THUỐC), có thể chứa các nhãn: "isNegated", "isHistorical", "isFamily".
5. `candidates`: Mảng chứa mã chuẩn hóa (ICD-10 cho CHẨN_ĐOÁN, RxNorm cho THUỐC).

Văn bản lâm sàng:
\"\"\"
{text}
\"\"\""""

        outputs = self.llm_pipeline(
            prompt, 
            max_new_tokens=1024, 
            do_sample=False,
            return_full_text=False
        )
        generated_text = outputs[0]['generated_text']
        
        # Parse JSON structure from LLM output
        try:
            # Clean possible markdown wrap ```json ... ```
            clean_json = re.sub(r'^```json\s*|```$', '', generated_text.strip(), flags=re.MULTILINE)
            return json.loads(clean_json)
        except Exception as e:
            print(f"❌ Lỗi parse JSON từ đầu ra LLM: {e}. Trả về danh sách rỗng.")
            return []

    def run_phobert_inference(self, text):
        """
        Calls PhoBERT NER model to get high precision spans.
        """
        if not self.phobert_pipeline:
            # Mock PhoBERT return for development testing
            return [
                {"text": "tăng huyết áp", "position": [14, 27], "type": "CHẨN_ĐOÁN"},
                {"text": "Aspirin", "position": [40, 47], "type": "THUỐC"}
            ]
            
        results = self.phobert_pipeline(text)
        phobert_entities = []
        for ent in results:
            phobert_entities.append({
                "text": ent["word"],
                "position": [ent["start"], ent["end"]],
                "type": ent["entity_group"]
            })
        return phobert_entities

    def split_text_into_chunks(self, text, max_words=256, overlap_words=60):
        """
        Cơ chế Cửa sổ trượt gối đầu (Overlap Sliding Window):
        Cắt văn bản thành các đoạn tối đa 256 từ, nhưng mỗi đoạn sau sẽ lấy gối đầu
        60 từ của đoạn trước để mang theo ngữ cảnh (phủ định, lịch sử bệnh...).
        """
        words_data = []
        # Tách từ kèm theo chỉ số ký tự để ánh xạ chính xác
        for m in re.finditer(r'\S+', text):
            words_data.append({
                "word": m.group(),
                "start": m.start(),
                "end": m.end()
            })
            
        if not words_data:
            return [{"text": text, "start_offset": 0}]
            
        chunks = []
        total_words = len(words_data)
        start_idx = 0
        
        while start_idx < total_words:
            end_idx = min(start_idx + max_words, total_words)
            
            # Lấy vị trí ký tự bắt đầu và kết thúc của chunk
            char_start = words_data[start_idx]["start"]
            char_end = words_data[end_idx - 1]["end"]
            
            chunks.append({
                "text": text[char_start:char_end],
                "start_offset": char_start
            })
            
            # Dịch chuyển cửa sổ trượt: Tiến lên (max_words - overlap_words) từ
            if end_idx == total_words:
                break
            start_idx = end_idx - overlap_words
            
        return chunks

    def validate_and_align_positions(self, entities, original_text):
        """
        Kiểm tra và sửa lỗi vị trí ký tự của thực thể trích xuất.
        Đảm bảo original_text[start:end] khớp chính xác với entity text.
        Nếu lệch vị trí do LLM gán sai chỉ số, tự động dịch chuyển về vị trí đúng gần nhất.
        Nếu từ bị ảo giác (không tồn tại trong văn bản gốc), tự động loại bỏ để tránh trừ điểm.
        """
        valid_entities = []
        for ent in entities:
            text = ent.get("text", "").strip()
            if not text:
                continue
            pos = ent.get("position", [0, 0])
            start, end = pos[0], pos[1]
            
            # 1. Kiểm tra xem vị trí hiện tại có khớp chính xác không
            sub_text = original_text[start:end].strip()
            if sub_text.lower() == text.lower():
                ent["text"] = sub_text  # Đồng bộ hóa chữ hoa/thường chuẩn xác
                valid_entities.append(ent)
                continue
                
            # 2. Lệch vị trí: Tìm kiếm cụm từ đó trong toàn bộ văn bản gốc
            matches = [m.start() for m in re.finditer(re.escape(text), original_text, re.IGNORECASE)]
            if matches:
                closest_start = min(matches, key=lambda x: abs(x - start))
                new_end = closest_start + len(text)
                ent["position"] = [closest_start, new_end]
                ent["text"] = original_text[closest_start:new_end]
                valid_entities.append(ent)
                continue
                
            # 3. Lỗi vị trí lệch nhỏ (sai lệch lệch khoảng vài ký tự do khoảng trắng)
            search_start = max(0, start - 20)
            search_end = min(len(original_text), end + 20)
            window_text = original_text[search_start:search_end]
            
            match_in_window = re.search(re.escape(text), window_text, re.IGNORECASE)
            if match_in_window:
                new_start = search_start + match_in_window.start()
                new_end = new_start + len(text)
                ent["position"] = [new_start, new_end]
                ent["text"] = original_text[new_start:new_end]
                valid_entities.append(ent)
                continue
                
            print(f"⚠️ Đã loại bỏ thực thể ảo giác của LLM: '{text}' (không tìm thấy trong văn bản gốc)")
            
        return valid_entities

    def process_document(self, text):
        # Tách tài liệu thành các chunks nhỏ hơn để tối ưu hóa trích xuất
        chunks = self.split_text_into_chunks(text, max_words=256, overlap_words=60)
        
        all_llm_ents = []
        all_phobert_ents = []
        
        for chunk in chunks:
            chunk_text = chunk["text"]
            offset = chunk["start_offset"]
            
            # 1. Trích xuất LLM trên từng chunk
            llm_ents = self.run_llm_inference(chunk_text)
            for ent in llm_ents:
                pos = ent.get("position", [0, 0])
                ent["position"] = [pos[0] + offset, pos[1] + offset]
                all_llm_ents.append(ent)
                
            # 2. Trích xuất PhoBERT trên từng chunk (tránh bị cắt cụt do giới hạn max_length)
            phobert_ents = self.run_phobert_inference(chunk_text)
            for ent in phobert_ents:
                pos = ent.get("position", [0, 0])
                ent["position"] = [pos[0] + offset, pos[1] + offset]
                all_phobert_ents.append(ent)
                
        # 3. Xác thực vị trí và loại bỏ thực thể ảo giác
        valid_llm_ents = self.validate_and_align_positions(all_llm_ents, text)
        valid_phobert_ents = self.validate_and_align_positions(all_phobert_ents, text)
        
        # 4. Ensemble Merger (Đồng bộ hóa ranh giới thực thể và nhãn assertions)
        merged_ents = merge_entities(valid_llm_ents, valid_phobert_ents)
        
        # 5. Database Linker (Ghi đè mã ICD-10 & RxNorm chính xác từ CSDL)
        for ent in merged_ents:
            etype = ent.get("type", "")
            if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
                text_val = ent.get("text", "")
                codes = self.linker.link_entity(text_val, etype)
                ent["candidates"] = codes
                
        return merged_ents

    def process_directory(self, input_dir=DEFAULT_INPUT_DIR, output_dir=DEFAULT_OUTPUT_DIR):
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        txt_files = list(input_path.glob("*.txt"))
        if not txt_files:
            print(f"⚠️ Không tìm thấy tệp văn bản .txt nào trong {input_path}")
            return
            
        print(f"Bắt đầu xử lý {len(txt_files)} tệp trong {input_path}...")
        for f in txt_files:
            text = f.read_text(encoding="utf-8")
            result = self.process_document(text)
            
            # Save corresponding json output
            out_f = output_path / f"{f.stem}.json"
            with open(out_f, "w", encoding="utf-8") as out_file:
                json.dump(result, out_file, ensure_ascii=False, indent=2)
            print(f"  -> Đã ghi kết quả: {out_f.name}")
        print("🎉 Xử lý toàn bộ thư mục thành công!")

    def close(self):
        self.linker.close()

if __name__ == "__main__":
    pipeline_runner = EndToEndPipeline(use_semantic_linker=False)
    sample_text = "Tiền sử bệnh: bệnh nhân bị tăng huyết áp 2 năm. Đơn thuốc kê đơn: Aspirin 100mg hàng ngày."
    res = pipeline_runner.process_document(sample_text)
    print("\nKết quả xử lý mẫu thử nghiệm:")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    pipeline_runner.close()
