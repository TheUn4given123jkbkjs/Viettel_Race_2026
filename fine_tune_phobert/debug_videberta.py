import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Import train_videberta first (which imports datasets before torch to prevent Windows DLL conflicts)
from train_videberta import VidebertaCRFForTokenClassification, tokenize_and_align_labels, read_jsonl, LABEL_LIST, LABEL_TO_ID, ID_TO_LABEL, MODEL_NAME

import torch
import torch.nn as nn
torch.set_num_threads(1)
from datasets import Dataset
from transformers import AutoTokenizer

def debug():
    print("=== DEBUGGING VIDEBERTA-CRF STABILITY ===")
    
    # Enable anomaly detection
    torch.autograd.set_detect_anomaly(True)
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "fine_tune_phobert")
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    
    train_data = read_jsonl(os.path.join(DATA_DIR, "train_phobert.jsonl"))[:4]
    
    encodings = tokenizer(
        [ex["tokens"] for ex in train_data],
        truncation=True,
        is_split_into_words=True,
        max_length=128
    )
    
    labels = []
    for i, ex in enumerate(train_data):
        word_ids = encodings.word_ids(batch_index=i)
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != previous_word_idx:
                label_ids.append(ex["ner_tags"][word_idx])
            else:
                label_ids.append(-100)
            previous_word_idx = word_idx
        labels.append(label_ids)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Using device:", device)
    
    input_ids = torch.tensor(encodings["input_ids"]).to(device)
    attention_mask = torch.tensor(encodings["attention_mask"]).to(device)
    batch_labels = torch.tensor(labels).to(device)
    
    print("\nInitializing model...")
    model = VidebertaCRFForTokenClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABEL_LIST),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
        torch_dtype=torch.float32
    ).to(device)
    
    # Define optimizer
    deberta_params = []
    classifier_params = []
    crf_params = []
    for name, param in model.named_parameters():
        if "deberta" in name:
            deberta_params.append(param)
        elif "classifier" in name:
            classifier_params.append(param)
        elif "crf" in name:
            crf_params.append(param)
            
    optimizer_grouped_parameters = [
        {"params": deberta_params, "lr": 2e-5},
        {"params": classifier_params, "lr": 1e-4},
        {"params": crf_params, "lr": 2e-4},
    ]
    optimizer = torch.optim.AdamW(optimizer_grouped_parameters, weight_decay=0.01)
    
    print("\nStarting 10 debug training steps...")
    for step in range(1, 11):
        optimizer.zero_grad()
        
        # Forward pass through model directly to check CRF loss calculation
        outputs_deberta = model.deberta(input_ids, attention_mask=attention_mask)
        seq_output = model.dropout(outputs_deberta[0])
        emissions = model.classifier(seq_output)
        
        print("Forward pass diagnostics:")
        print(f"  DeBERTa outputs contains NaN: {torch.isnan(outputs_deberta[0]).any().item()}")
        print(f"  seq_output contains NaN: {torch.isnan(seq_output).any().item()}")
        print(f"  emissions contains NaN: {torch.isnan(emissions).any().item()}")
        print(f"  emissions range: Min={emissions.min().item():.4f}, Max={emissions.max().item():.4f}")
        
        clean_labels = batch_labels.clone()
        clean_labels[clean_labels == -100] = 0
        mask = attention_mask.bool()
        loss = -model.crf(emissions, clean_labels, mask=mask, reduction='token_mean')
        
        print(f"\nStep {step} - Loss: {loss.item()}")
        
        if torch.isnan(loss):
            print("ERROR: Loss is NaN!")
            break
            
        loss.backward()
        
        # Print detailed gradient stats
        print("\n=== LAYER NORM WEIGHT DIAGNOSTIC ===")
        ln_weight = model.deberta.embeddings.LayerNorm.weight
        print("LayerNorm.weight dtype:", ln_weight.dtype)
        print("LayerNorm.weight before step:", ln_weight.data[:5].tolist())
        print("LayerNorm.weight.grad before step:", ln_weight.grad[:5].tolist())
        print("LayerNorm.weight contains NaN:", torch.isnan(ln_weight).any().item())
        print("LayerNorm.weight.grad contains NaN:", torch.isnan(ln_weight.grad).any().item())
        
        # Clip gradients
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        print("LayerNorm.weight.grad after clipping:", ln_weight.grad[:5].tolist())
        
        # Optimizer state
        print("Optimizer param group details:")
        for i, group in enumerate(optimizer.param_groups):
            print(f"  Group {i} LR: {group['lr']}, weight_decay: {group['weight_decay']}")
            print(f"  Group {i} eps: {group.get('eps', 'N/A')}, betas: {group.get('betas', 'N/A')}")
            
        print("Optimizer state for ln_weight BEFORE step:", optimizer.state.get(ln_weight, "No state yet"))
        
        optimizer.step()
        
        print("Optimizer state for ln_weight AFTER step:")
        state = optimizer.state[ln_weight]
        for k, v in state.items():
            if isinstance(v, torch.Tensor):
                print(f"  {k}: shape={v.shape}, dtype={v.dtype}, min={v.min().item()}, max={v.max().item()}, contains_nan={torch.isnan(v).any().item()}")
            else:
                print(f"  {k}: {v}")
                
        print("LayerNorm.weight after step:", ln_weight.data[:5].tolist())
        print("LayerNorm.weight contains NaN after step:", torch.isnan(ln_weight).any().item())
        print("=== END DIAGNOSTIC ===")
        break

if __name__ == "__main__":
    debug()
