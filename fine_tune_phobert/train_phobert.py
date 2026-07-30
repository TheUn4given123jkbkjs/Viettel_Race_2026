import os
import json
import torch
import numpy as np
from datasets import load_dataset, Dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForTokenClassification, 
    TrainingArguments, 
    Trainer,
    DataCollatorForTokenClassification
)
import evaluate

# Path configuration
BASE_DIR = "d:/record_by_me/Viettel_race"
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
    # PhoBERT tokenizer expects pre-tokenized words as input when is_split_into_words=True
    tokenized_inputs = tokenizer(
        examples["tokens"], 
        truncation=True, 
        is_split_into_words=True,
        max_length=256
    )

    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            # Special tokens are mapped to None. We set their label to -100 to ignore in loss calculation.
            if word_idx is None:
                label_ids.append(-100)
            # We set the label for the first subword token of each word.
            elif word_idx != previous_word_idx:
                label_ids.append(label[word_idx])
            # For subsequent subwords of the same word, we set label to -100 as well.
            else:
                label_ids.append(-100)
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
    # Process in batches
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
        evaluation_strategy="epoch",
        learning_rate=5e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=5,
        weight_decay=0.01,
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        report_to="none"  # Disable wandb/tensorboard logging for clean output
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=val_tokenized,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    print("Starting training...")
    trainer.train()

    print(f"Saving best model to {OUTPUT_MODEL_DIR}...")
    trainer.save_model(OUTPUT_MODEL_DIR)
    tokenizer.save_pretrained(OUTPUT_MODEL_DIR)
    print("Training finished successfully!")

if __name__ == "__main__":
    main()
