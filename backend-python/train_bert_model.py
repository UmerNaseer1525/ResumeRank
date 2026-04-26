from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
from typing import Any

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split


MODEL_DIR = Path(__file__).resolve().parent / "app" / "models" / "resume_ranker_bert"


def seed_everything(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:
        pass

    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


def load_supervised_jsonl(path: Path, limit: int | None = None) -> tuple[list[str], list[int]]:
    if not path.exists():
        raise RuntimeError(f"Dataset not found: {path}")

    texts: list[str] = []
    labels: list[int] = []
    has_explicit_labels = False
    has_messages_format = False

    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if limit and len(texts) >= limit:
                break

            raw = line.strip()
            if not raw:
                continue

            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if not isinstance(item, dict):
                continue

            # Try supervised format first (resume_text + explicit label)
            text = str(item.get("resume_text", "") or "").strip()
            label_raw = item.get("label")

            if text and label_raw in [0, 1, "0", "1", False, True]:
                label = 1 if str(label_raw).lower() in {"1", "true"} else 0
                texts.append(text)
                labels.append(label)
                has_explicit_labels = True
                continue

            # Try chat-style format (messages array with role/content pairs)
            messages = item.get("messages")
            if isinstance(messages, list) and len(messages) > 0:
                has_messages_format = True
                
                # Preserve full conversation with clear role markers for quality assessment
                conversation_text = ""
                for msg in messages:
                    if isinstance(msg, dict):
                        role = msg.get("role", "").lower()
                        content = str(msg.get("content", "")).strip()
                        
                        if role == "user":
                            conversation_text += f"[Question] {content} "
                        elif role == "assistant":
                            conversation_text += f"[Response] {content} "
                
                if conversation_text.strip():
                    texts.append(conversation_text.strip())

    # If we have explicit labels, we're done
    if has_explicit_labels:
        return texts, labels
    
    # If we found chat-style messages, apply intelligent resume-relevance labeling
    if has_messages_format and texts:
        print(f"[INFO] Auto-detected chat conversations. Evaluating discussion quality for hiring signals...")
        
        # ===== ENHANCED HIRING QUALITY SIGNALS =====
        
        # TIER 1: Technical Depth (Shows understanding of fundamentals)
        tech_depth_signals = {
            # Architecture & Design
            'architecture', 'design pattern', 'microservice', 'monolith',
            'scalability', 'reliability', 'fault tolerance', 'load balancing',
            
            # Algorithms & Optimization
            'algorithm', 'complexity', 'optimization', 'performance', 'bottleneck',
            'efficient', 'big-o', 'runtime', 'memory footprint', 'trade-off',
            
            # System Design
            'database', 'sql', 'nosql', 'cache', 'queue', 'message broker',
            'api', 'rest', 'graphql', 'websocket', 'protocol',
            
            # Code Quality
            'refactor', 'clean code', 'solid', 'design principle', 'testing',
            'unit test', 'integration test', 'mock', 'stub',
        }
        
        # TIER 2: Problem-Solving & Communication
        problem_solving_signals = {
            # Structured thinking
            'first consider', 'approach', 'methodology', 'break down',
            'identify', 'analyze', 'evaluate', 'compare', 'trade-off',
            'pros and cons', 'advantages', 'disadvantages', 'implications',
            
            # Clear explanations
            'specifically', 'for example', 'let me explain', 'essentially',
            'in other words', 'more precisely', 'to clarify', 'furthermore',
            
            # Evidence of depth
            'real-world', 'production', 'i encountered', 'we handled',
            'my experience', 'i implemented', 'we built',
        }
        
        # TIER 3: Practical Experience
        practical_signals = {
            # Scale & Impact
            'production', 'deployed', 'users', 'scale', 'thousands', 'millions',
            'incident', 'outage', 'monitoring', 'alerting', 'observability',
            
            # Collaboration
            'team', 'collaborate', 'coordinate', 'code review', 'pair programming',
            'mentored', 'led', 'managed', 'stakeholder',
            
            # DevOps & Infrastructure
            'ci/cd', 'docker', 'kubernetes', 'deployment', 'infrastructure',
            'automation', 'pipeline', 'regression', 'load test',
        }
        
        # TIER 4: Growth Mindset
        learning_signals = {
            'learned', 'improvement', 'evolved', 'challenge', 'overcome',
            'mistake', 'failure', 'growth', 'research', 'experiment',
            'iterate', 'refine', 'better approach', 'optimized',
        }
        
        # Anti-signals (Generic/Low Quality)
        red_flags = {
            'basically', 'kind of', 'just', 'simply', 'pretty much',
            'obviously', 'of course', 'everyone knows', 'trivial',
            'idk', 'not sure', 'dunno', 'no idea', 'never tried',
            'probably', 'maybe', 'might', 'could be', 'i guess',
        }
        
        positive_count = 0
        for text in texts:
            text_lower = text.lower()
            
            # ===== MULTI-TIER SCORING =====
            
            # Tier 1: Technical depth (most important for engineers)
            tech_score = sum(1 for signal in tech_depth_signals if signal in text_lower)
            
            # Tier 2: Problem-solving & communication
            problem_score = sum(1 for signal in problem_solving_signals if signal in text_lower)
            
            # Tier 3: Practical experience
            practical_score = sum(1 for signal in practical_signals if signal in text_lower)
            
            # Tier 4: Growth mindset
            learning_score = sum(1 for signal in learning_signals if signal in text_lower)
            
            # Penalties for red flags
            red_flag_count = sum(1 for flag in red_flags if flag in text_lower)
            
            # Check response depth and substantive content
            word_count = len(text.split())
            is_substantive = word_count > 50  # Response has real substance
            
            # Check for multi-faceted answers (mentions multiple angles)
            has_depth = '[response]' in text_lower and '[question]' in text_lower
            response_count = text_lower.count('[response]')
            
            # ===== FINAL LABEL DETERMINATION =====
            # Weighted scoring: Tech > Problem-solving > Practical > Learning
            weighted_score = (
                tech_score * 3 +
                problem_score * 2 +
                practical_score * 1.5 +
                learning_score * 1
            ) - (red_flag_count * 2)
            
            # Composite signal: substantive + depth + score threshold
            is_high_quality = (
                is_substantive and
                has_depth and
                weighted_score >= 3
            ) or weighted_score >= 5
            
            
            # Check if it's a question (user asking) vs response (assistant)
            has_responses = '[Response]' in text and len([x for x in text.split('[Response]') if len(x.strip()) > 20]) > 0
            
            # ===== HIRING DECISION LOGIC =====
            # Positive: High technical depth OR strong problem-solving + substantive response
            # This identifies candidates who demonstrate real expertise and communication
            hire = is_high_quality and has_responses
            
            label = 1 if hire else 0
            labels.append(label)
            if label == 1:
                positive_count += 1
        
        print(f"[INFO] Smart discussion evaluation: {positive_count} high-quality, {len(labels) - positive_count} lower-quality (ratio: {positive_count/len(labels)*100:.1f}%)")
        return texts, labels
    
    # Fallback: if no texts found at all
    if not texts:
        raise RuntimeError(f"No valid records found in {path}")
    
    return texts, labels


def train_bert(
    dataset_path: Path,
    limit: int | None,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_length: int,
    seed: int,
) -> None:
    seed_everything(seed)

    # Auto-fallback to supervised dataset if it exists and raw data doesn't have enough labels
    if not dataset_path.exists():
        supervised_fallback = Path(__file__).resolve().parent / "data" / "resume_supervised.jsonl"
        if supervised_fallback.exists():
            print(f"[INFO] Dataset not found: {dataset_path}")
            print(f"[INFO] Falling back to: {supervised_fallback}")
            dataset_path = supervised_fallback
        else:
            raise RuntimeError(f"Dataset not found: {dataset_path}")

    texts, labels = load_supervised_jsonl(dataset_path, limit=limit)
    
    # If heuristic labeling resulted in only one class, try supervised dataset as fallback
    if len(set(labels)) < 2:
        supervised_fallback = Path(__file__).resolve().parent / "data" / "resume_supervised.jsonl"
        if supervised_fallback.exists() and supervised_fallback != dataset_path:
            print(f"[INFO] Only one class in dataset. Falling back to supervised dataset: {supervised_fallback}")
            texts, labels = load_supervised_jsonl(supervised_fallback, limit=limit)
    
    if len(texts) < 20:
        raise RuntimeError("Need at least 20 labeled rows for transformer training.")
    if len(set(labels)) < 2:
        raise RuntimeError("Need both classes (0 and 1) in dataset.")

    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
    )

    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    train_texts, eval_texts, train_labels, eval_labels = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=seed,
        stratify=labels,
    )

    train_dataset = Dataset.from_dict({"text": train_texts, "label": train_labels})
    eval_dataset = Dataset.from_dict({"text": eval_texts, "label": eval_labels})

    def tokenize_fn(batch: dict[str, Any]) -> dict[str, Any]:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
        )

    train_dataset = train_dataset.map(tokenize_fn, batched=True)
    eval_dataset = eval_dataset.map(tokenize_fn, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    def compute_metrics(eval_pred: Any) -> dict[str, float]:
        logits, y_true = eval_pred
        import numpy as np

        y_pred = np.argmax(logits, axis=-1)
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        }

    training_args = TrainingArguments(
        output_dir=str(MODEL_DIR / "_training_output"),
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="no",
        logging_strategy="epoch",
        load_best_model_at_end=False,
        report_to=[],
        seed=seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    predictions = trainer.predict(eval_dataset)
    logits = predictions.predictions

    import numpy as np

    y_pred = np.argmax(logits, axis=-1)
    y_true = np.array(eval_labels)

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "mae": None,
        "r2": None,
        "cvF1": None,
        "sampleCount": len(texts),
        "positiveLabelCount": int(sum(labels)),
        "negativeLabelCount": int(len(labels) - sum(labels)),
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(MODEL_DIR))
    tokenizer.save_pretrained(str(MODEL_DIR))

    metadata = {
        "version": 1,
        "kind": "bert_sequence_classifier_v1",
        "task": "binary_relevance",
        "threshold": 0.5,
        "baseModel": model_name,
        "max_length": max_length,
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "datasetSource": str(dataset_path),
        "metrics": metrics,
    }

    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("BERT model training complete")
    print(f"Model dir: {MODEL_DIR}")
    print(f"Samples: {len(texts)}")
    print(f"Accuracy: {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall: {metrics['recall']:.3f}")
    print(f"F1: {metrics['f1']:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train DistilBERT resume relevance model")
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/resume_supervised.jsonl",
        help="Path to supervised JSONL dataset",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max rows to load")
    parser.add_argument("--epochs", type=int, default=2, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--learning-rate", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--max-length", type=int, default=256, help="Max token length")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    train_bert(
        dataset_path=dataset_path,
        limit=args.limit or None,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        seed=args.seed,
    )
