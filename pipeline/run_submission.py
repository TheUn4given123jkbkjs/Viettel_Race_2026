import os
import sys
from pathlib import Path

# Resolve paths
PIPELINE_DIR = Path(__file__).parent
BASE_DIR = PIPELINE_DIR.parent
sys.path.append(str(PIPELINE_DIR))

from run_pipeline import EndToEndPipeline

def main():
    print("=" * 80)
    print("  RUNNING PIPELINE SUBMISSION FOR TURN 2 VONG 1")
    print("=" * 80)

    # Path to the best PhoBERT model (Baseline checkpoint 4630 with 56.08% F1)
    phobert_model_path = str(BASE_DIR / "fine_tune_phobert" / "results_old" / "checkpoint-4630")
    
    # Check if the baseline model directory exists
    if not os.path.exists(phobert_model_path):
        print(f"⚠️ Model baseline not found at {phobert_model_path}. Fallback to fine-tuned phobert_ner_model.")
        phobert_model_path = str(BASE_DIR / "fine_tune_phobert" / "phobert_ner_model")
        
    input_dir = str(BASE_DIR / "input_turn2_vong1" / "input")
    output_dir = str(BASE_DIR / "input_turn2_vong1" / "output")

    print(f"Model path: {phobert_model_path}")
    print(f"Input dir:  {input_dir}")
    print(f"Output dir: {output_dir}")

    # Initialize EndToEndPipeline
    pipeline_runner = EndToEndPipeline(
        phobert_model_path=phobert_model_path,
        use_semantic_linker=False
    )

    # Process all 100 files in the directory
    pipeline_runner.process_directory(input_dir=input_dir, output_dir=output_dir)
    pipeline_runner.close()
    
    print("\n🎉 Output files successfully generated in input_turn2_vong1/output!")

if __name__ == "__main__":
    main()
