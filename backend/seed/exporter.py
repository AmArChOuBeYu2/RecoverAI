"""
Synthetic Dataset Exporter for RecoverAI
Saves generated dataset partitions into isolated directory boundaries:
data/observed/, data/holdout/, data/simulation_truth/, data/metadata/.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from backend.seed.config import GeneratorConfig

def export_synthetic_dataset(
    config: GeneratorConfig,
    base_dir: Path,
    customers: List[Dict[str, Any]],
    train_txns: List[Dict[str, Any]],
    holdout_txns: List[Dict[str, Any]],
    train_outcomes: List[Dict[str, Any]],
    holdout_outcomes: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> Dict[str, Path]:
    """Export dataset components to disk with explicit strict separation."""
    
    observed_dir = base_dir / "data" / "observed"
    holdout_dir = base_dir / "data" / "holdout"
    truth_dir = base_dir / "data" / "simulation_truth"
    meta_dir = base_dir / "data" / "metadata"

    for d in [observed_dir, holdout_dir, truth_dir, meta_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. Observed Train Dataset
    _write_json(observed_dir / "customers.json", customers)
    _write_json(observed_dir / "transactions.json", train_txns)
    _write_json(observed_dir / "outcomes.json", train_outcomes)
    _write_json(observed_dir / "segments.json", segments)

    # 2. Holdout Test Dataset
    _write_json(holdout_dir / "transactions.json", holdout_txns)
    _write_json(holdout_dir / "outcomes.json", holdout_outcomes)

    # 3. Hidden Simulation Ground Truth (ISOLATED)
    _write_json(truth_dir / "ground_truth.json", ground_truth)

    # 4. Dataset Metadata
    metadata = {
        "dataset_version": config.dataset_version,
        "generator_version": config.generator_version,
        "seed": config.seed,
        "total_transactions": len(train_txns) + len(holdout_txns),
        "train_transactions_count": len(train_txns),
        "holdout_transactions_count": len(holdout_txns),
        "customers_count": len(customers),
        "generated_at": stats["generated_at"],
        "data_source": "SYNTHETIC_SIMULATION",
        "split_definition": {
            "historical_train_ratio": config.historical_ratio,
            "temporal_holdout_ratio": round(1.0 - config.historical_ratio, 2),
            "split_method": "CHRONOLOGICAL_CREATION_TIME",
        },
        "stats": stats,
    }
    _write_json(meta_dir / "dataset_metadata.json", metadata)

    return {
        "observed": observed_dir,
        "holdout": holdout_dir,
        "truth": truth_dir,
        "metadata": meta_dir,
    }

def _write_json(path: Path, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
