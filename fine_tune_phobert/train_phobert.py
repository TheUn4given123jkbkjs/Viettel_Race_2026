from datasets import Dataset
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import evaluate
import os
import json
import torch
import numpy as np
from transformers import (
    AutoTokenizer, 
    TrainingArguments, 
    Trainer,
    DataCollatorForTokenClassification,
    AutoModelForTokenClassification
)

# Path configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "fine_tune_phobert")
OUTPUT_MODEL_DIR = os.path.join(DATA_DIR, "phobert_ner_model")

# Load label mapping
with open(os.path.join(DATA_DIR, "label_mapping.json"), "r", encoding="utf-8") as f:
    mapping = json.load(f)
    LABEL_TO_ID = mapping["label_to_id"]
    ID_TO_LABEL = {int(k): v for k, v in mapping["id_to_label"].items()}
    LABEL_LIST = list(LABEL_TO_ID.keys())

# Load tokenizer
MODEL_NAME = "vinai/phobert-base"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)

def read_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line.strip()))
    return data

def tokenize_and_align_labels(examples):
    tokenized_inputs = tokenizer(
        examples["tokens"], 
        truncation=True, 
        is_split_into_words=True,
        max_length=256
    )

    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        words = examples["tokens"][i]
        
        # Build manual word_ids mapping
        word_ids = [None]  # <s> at start
        for word_idx, word in enumerate(words):
            # Tokenize individual word
            subwords = tokenizer.tokenize(word)
            # Add word_idx for each subword token
            word_ids.extend([word_idx] * len(subwords))
        word_ids.append(None)  # </s> at end
        
        # Truncate/pad word_ids to match input_ids length
        input_ids_len = len(tokenized_inputs["input_ids"][i])
        word_ids = word_ids[:input_ids_len]
        if len(word_ids) < input_ids_len:
            word_ids.extend([None] * (input_ids_len - len(word_ids)))
        
        previous_word_idx = None
        curr_label = 0
        label_ids = []
        for word_idx in word_ids:
            # Special tokens mapped to -100 to ignore in loss calculation
            if word_idx is None:
                label_ids.append(-100)
            # First subword token gets the actual label
            elif word_idx != previous_word_idx:
                label_ids.append(label[word_idx])
                curr_label = label[word_idx]
            # Subsequent subwords get corresponding tag to maintain valid transitions
            else:
                if curr_label % 2 == 1:
                    label_ids.append(curr_label + 1)
                else:
                    label_ids.append(curr_label)
            previous_word_idx = word_idx
        labels.append(label_ids)

    tokenized_inputs["labels"] = labels
    return tokenized_inputs

# Metric calculation
seqeval = evaluate.load("seqeval")

def compute_metrics(p):
    predictions, labels = p
    predictions = np.argmax(predictions, axis=2)

    true_predictions = [
        [LABEL_LIST[p] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]
    true_labels = [
        [LABEL_LIST[l] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]

    results = seqeval.compute(predictions=true_predictions, references=true_labels)
    return {
        "precision": results["overall_precision"],
        "recall": results["overall_recall"],
        "f1": results["overall_f1"],
        "accuracy": results["overall_accuracy"],
    }

def main():
    print("Loading datasets...")
    train_data = read_jsonl(os.path.join(DATA_DIR, "train_phobert.jsonl"))
    val_data = read_jsonl(os.path.join(DATA_DIR, "val_phobert.jsonl"))

    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data)

    print("Tokenizing and aligning labels...")
    train_tokenized = train_dataset.map(tokenize_and_align_labels, batched=True, remove_columns=["tokens", "ner_tags"])
    val_tokenized = val_dataset.map(tokenize_and_align_labels, batched=True, remove_columns=["tokens", "ner_tags"])

    print("Initializing model...")
    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABEL_LIST),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID
    )

    data_collator = DataCollatorForTokenClassification(tokenizer)

    training_args = TrainingArguments(
        output_dir=os.path.join(DATA_DIR, "results"),
        eval_strategy="epoch",
        learning_rate=5e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=10,
        weight_decay=0.01,
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        fp16=torch.cuda.is_available(),
        report_to="none"
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=val_tokenized,
        processing_class=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics
    )

    print("Starting training from scratch...")
    trainer.train()

    print(f"Saving best model to {OUTPUT_MODEL_DIR}...")
    trainer.save_model(OUTPUT_MODEL_DIR)
    tokenizer.save_pretrained(OUTPUT_MODEL_DIR)
    print("Training finished successfully!")

if __name__ == "__main__":
    main()
