from datasets import load_dataset, Dataset
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import evaluate
import os
import json
import torch
import torch.nn as nn
import numpy as np
from torchcrf import CRF
from transformers import (
    AutoTokenizer, 
    TrainingArguments, 
    Trainer,
    DataCollatorForTokenClassification,
    DebertaV2PreTrainedModel,
    DebertaV2Model
)
from transformers.modeling_outputs import TokenClassifierOutput

# Custom model class with CRF Layer for DebertaV2
class VidebertaCRFForTokenClassification(DebertaV2PreTrainedModel):
    _keys_to_ignore_on_load_unexpected = [r"pooler"]

    def __init__(self, config):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.deberta = DebertaV2Model(config)
        classifier_dropout = (
            getattr(config, "classifier_dropout", None)
            if getattr(config, "classifier_dropout", None) is not None
            else getattr(config, "hidden_dropout_prob", 0.1)
        )
        self.dropout = nn.Dropout(classifier_dropout)
        self.classifier = nn.Linear(config.hidden_size, config.num_labels)
        
        # CRF Layer
        self.crf = CRF(config.num_labels, batch_first=True)
        
        # Dynamic Class Weights placeholder
        self.register_buffer("class_weights", torch.ones(config.num_labels))
        
        # Initialize weights
        self.post_init()

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        position_ids=None,
        inputs_embeds=None,
        labels=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
    ):
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict

        outputs = self.deberta(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            position_ids=position_ids,
            inputs_embeds=inputs_embeds,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )

        sequence_output = outputs[0]
        sequence_output = self.dropout(sequence_output)
        emissions = self.classifier(sequence_output)

        loss = None
        if labels is not None:
            clean_labels = labels.clone()
            clean_labels[clean_labels == -100] = 0
            mask = attention_mask.bool()
            # Minimize negative log-likelihood
            loss = -self.crf(emissions, clean_labels, mask=mask, reduction='token_mean')

        # During evaluation / inference, return dummy logits that map to the decoded CRF path
        if not self.training:
            mask = attention_mask.bool()
            decoded_paths = self.crf.decode(emissions, mask=mask)
            
            batch_size, seq_len, num_labels = emissions.shape
            logits = torch.zeros(batch_size, seq_len, num_labels, device=emissions.device)
            for i, path in enumerate(decoded_paths):
                for t, tag_id in enumerate(path):
                    logits[i, t, tag_id] = 10.0
                if len(path) < seq_len:
                    logits[i, len(path):, 0] = 10.0
        else:
            logits = emissions

        if not return_dict:
            output = (logits,) + outputs[2:]
            return ((loss,) + output) if loss is not None else output

        return TokenClassifierOutput(
            loss=loss,
            logits=logits,
            hidden_states=outputs.hidden_states,
            attentions=outputs.attentions,
        )

# Path configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "fine_tune_phobert")
OUTPUT_MODEL_DIR = os.path.join(DATA_DIR, "videberta_ner_model")

# Load label mapping
with open(os.path.join(DATA_DIR, "label_mapping.json"), "r", encoding="utf-8") as f:
    mapping = json.load(f)
    LABEL_TO_ID = mapping["label_to_id"]
    ID_TO_LABEL = {int(k): v for k, v in mapping["id_to_label"].items()}
    LABEL_LIST = list(LABEL_TO_ID.keys())

# Load tokenizer
MODEL_NAME = "Fsoft-AIC/videberta-base"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)

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
        max_length=128
    )

    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            # Special tokens mapped to -100
            if word_idx is None:
                label_ids.append(-100)
            # First subword token gets the actual label
            elif word_idx != previous_word_idx:
                label_ids.append(label[word_idx])
            # Subsequent subwords get -100
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
    train_tokenized = train_dataset.map(tokenize_and_align_labels, batched=True, remove_columns=["tokens", "ner_tags"])
    val_tokenized = val_dataset.map(tokenize_and_align_labels, batched=True, remove_columns=["tokens", "ner_tags"])

    print("Initializing ViDeBERTa model...")
    model = VidebertaCRFForTokenClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(LABEL_LIST),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
        torch_dtype=torch.float32
    )

    data_collator = DataCollatorForTokenClassification(tokenizer)

    # Configure custom optimizer with Layer-wise Learning Rate Decay (LLRD)
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

    # Configure custom Cosine Annealing scheduler
    num_train_epochs = 10
    batch_size = 16
    steps_per_epoch = len(train_tokenized) // batch_size
    num_training_steps = steps_per_epoch * num_train_epochs
    
    from transformers import get_cosine_schedule_with_warmup
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(0.1 * num_training_steps),
        num_training_steps=num_training_steps
    )

    training_args = TrainingArguments(
        output_dir=os.path.join(DATA_DIR, "results_videberta"),
        eval_strategy="epoch",
        learning_rate=2e-5,  # Dummy value
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        num_train_epochs=num_train_epochs,
        weight_decay=0.01,
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        report_to="none",
        fp16=False,
        bf16=False,
        max_grad_norm=1.0
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=val_tokenized,
        processing_class=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        optimizers=(optimizer, scheduler)
    )

    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"Trainer device: {trainer.args.device}")
    print(f"Model device: {next(model.parameters()).device}")
    print("Starting ViDeBERTa-CRF training...")
    trainer.train()

    print(f"Saving best model to {OUTPUT_MODEL_DIR}...")
    trainer.save_model(OUTPUT_MODEL_DIR)
    tokenizer.save_pretrained(OUTPUT_MODEL_DIR)
    print("Training finished successfully!")

if __name__ == "__main__":
    main()
