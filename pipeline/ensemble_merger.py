import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def compute_iou(pos1, pos2):
    """
    Calculate Intersection over Union (IoU) of two character spans [start, end].
    """
    s1, e1 = pos1
    s2, e2 = pos2
    
    # Overlap range
    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    
    if overlap_start >= overlap_end:
        return 0.0
        
    overlap = overlap_end - overlap_start
    union = (e1 - s1) + (e2 - s2) - overlap
    return overlap / union if union > 0 else 0.0

def merge_entities(llm_entities, phobert_entities, iou_threshold=0.5):
    """
    Ensemble merger pipeline:
    1. Align entities between LLM and PhoBERT using position overlap (IoU) and Type matching.
    2. Prefer PhoBERT's boundary (text/position) for aligned entities, while retaining LLM assertions.
    3. Include LLM-only and PhoBERT-only entities to maximize recall.
    """
    merged = []
    
    # Track which entities have been merged/matched
    matched_llm = set()
    matched_phobert = set()
    
    # Step 1: Find matching pairs (Type must match exactly, IoU >= threshold)
    for idx_l, ent_l in enumerate(llm_entities):
        type_l = ent_l.get("type", "")
        pos_l = ent_l.get("position", [0, 0])
        
        best_match_idx = -1
        best_iou = -1.0
        
        for idx_p, ent_p in enumerate(phobert_entities):
            if idx_p in matched_phobert:
                continue
            type_p = ent_p.get("type", "")
            if type_l != type_p:
                continue
                
            pos_p = ent_p.get("position", [0, 0])
            iou = compute_iou(pos_l, pos_p)
            
            if iou >= iou_threshold and iou > best_iou:
                best_iou = iou
                best_match_idx = idx_p
                
        if best_match_idx != -1:
            matched_llm.add(idx_l)
            matched_phobert.add(best_match_idx)
            ent_p = phobert_entities[best_match_idx]
            
            # Form aligned entity: PhoBERT boundaries + LLM assertions
            aligned_entity = {
                "text": ent_p.get("text", ""),
                "position": ent_p.get("position", [0, 0]),
                "type": type_l,
                "assertions": ent_l.get("assertions", []),
                "candidates": ent_l.get("candidates", []) # LLM candidates (if any)
            }
            merged.append(aligned_entity)
            
    # Step 2: Handle unmatched LLM entities (high value for assertions / negation)
    for idx_l, ent_l in enumerate(llm_entities):
        if idx_l not in matched_llm:
            merged.append(ent_l)
            
    # Step 3: Handle unmatched PhoBERT entities (high value for clinical terminology recall)
    for idx_p, ent_p in enumerate(phobert_entities):
        if idx_p not in matched_phobert:
            # Re-ensure assertions field is present
            if "assertions" not in ent_p:
                ent_p["assertions"] = []
            if "candidates" not in ent_p:
                ent_p["candidates"] = []
            merged.append(ent_p)
            
    # Sort merged list by start position to keep structure logical
    merged.sort(key=lambda x: x.get("position", [0, 0])[0])
    return merged

if __name__ == "__main__":
    # Sample Test case
    llm_sample = [
        {"text": "bị tăng huyết áp", "position": [10, 26], "type": "CHẨN_ĐOÁN", "assertions": ["isHistorical"], "candidates": ["I10"]},
        {"text": "không ho", "position": [50, 58], "type": "TRIỆU_CHỨNG", "assertions": ["isNegated"]}
    ]
    
    phobert_sample = [
        {"text": "tăng huyết áp", "position": [14, 26], "type": "CHẨN_ĐOÁN"},
        {"text": "sốt nhẹ", "position": [70, 77], "type": "TRIỆU_CHỨNG"}
    ]
    
    result = merge_entities(llm_sample, phobert_sample)
    print("Merged JSON Output:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
