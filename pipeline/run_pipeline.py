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

    def process_document(self, text):
        # 1. Extraction from LLM
        llm_ents = self.run_llm_inference(text)
        
        # 2. Extraction from PhoBERT
        phobert_ents = self.run_phobert_inference(text)
        
        # 3. Ensemble Merger (Align boundaries and assertions)
        merged_ents = merge_entities(llm_ents, phobert_ents)
        
        # 4. Database Linker (Inject ICD-10 & RxNorm codes)
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
