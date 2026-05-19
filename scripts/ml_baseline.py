from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd
from minio import Minio
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, MultiLabelBinarizer
from sklearn.compose import ColumnTransformer
from sklearn.base import BaseEstimator, TransformerMixin


MINIO_HOST = os.getenv("MINIO_HOST", "minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "minio_admin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "minio_admin_pw")
BUCKET = "datasets"


class MultiHotEncoder(BaseEstimator, TransformerMixin):
    def __init__(self) -> None:
        self.mlb = MultiLabelBinarizer()

    def fit(self, X, y=None):
        flat = [list(x) if x is not None else [] for x in X.iloc[:, 0]]
        self.mlb.fit(flat)
        return self

    def transform(self, X):
        flat = [list(x) if x is not None else [] for x in X.iloc[:, 0]]
        return self.mlb.transform(flat)


def load_latest_parquet(prefer_key: str | None = None) -> pd.DataFrame:
    client = Minio(MINIO_HOST, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)
    if prefer_key:
        obj = client.get_object(BUCKET, prefer_key)
        return pd.read_parquet(io.BytesIO(obj.read()))
    objects = sorted(
        client.list_objects(BUCKET, recursive=True),
        key=lambda o: o.last_modified,
        reverse=True,
    )
    parquets = [o for o in objects if o.object_name.endswith(".parquet")]
    if not parquets:
        raise SystemExit("no parquet en bucket datasets")
    target = parquets[0]
    print(f"using {target.object_name} ({target.size} bytes, modified {target.last_modified})")
    obj = client.get_object(BUCKET, target.object_name)
    return pd.read_parquet(io.BytesIO(obj.read()))


def build_features(df: pd.DataFrame):
    text = df["resumen_es"].fillna("").astype(str)
    ent = df[["entidades_normalizadas_es"]]
    return text, ent


def evaluate_model(name: str, model, X_text, X_ent, y) -> dict:
    pipeline = Pipeline([
        ("features", ColumnTransformer([
            ("text", TfidfVectorizer(ngram_range=(1, 2), max_features=2000, min_df=1), "resumen_es"),
            ("ent", MultiHotEncoder(), ["entidades_normalizadas_es"]),
        ])),
        ("clf", model),
    ])

    df = pd.DataFrame({"resumen_es": X_text, "entidades_normalizadas_es": X_ent["entidades_normalizadas_es"]})

    cv = StratifiedKFold(n_splits=min(5, min(Counter(y).values())), shuffle=True, random_state=42)
    scoring = {
        "f1_macro": "f1_macro",
        "recall_macro": "recall_macro",
    }
    scores = cross_validate(pipeline, df, y, cv=cv, scoring=scoring, n_jobs=1, return_train_score=False)

    pipeline.fit(df, y)
    y_pred = pipeline.predict(df)
    classes = sorted(set(y))
    per_class_recall = recall_score(y, y_pred, labels=classes, average=None, zero_division=0)
    recall_by_class = {c: float(r) for c, r in zip(classes, per_class_recall)}

    cm = confusion_matrix(y, y_pred, labels=classes).tolist()
    report = classification_report(y, y_pred, labels=classes, zero_division=0, output_dict=True)

    return {
        "model": name,
        "cv_f1_macro_mean": float(np.mean(scores["test_f1_macro"])),
        "cv_f1_macro_std": float(np.std(scores["test_f1_macro"])),
        "cv_recall_macro_mean": float(np.mean(scores["test_recall_macro"])),
        "train_recall_by_class": recall_by_class,
        "train_f1_macro": float(f1_score(y, y_pred, average="macro", zero_division=0)),
        "confusion_matrix_labels": classes,
        "confusion_matrix": cm,
        "classification_report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", default=None, help="key concreto en minIO; default: ultimo")
    parser.add_argument("--out", default="/tmp/ml_baseline_metrics.json")
    args = parser.parse_args()

    df = load_latest_parquet(args.parquet)
    print(f"shape: {df.shape}")
    df = df.dropna(subset=["triage_real"]).copy()
    print(f"after dropna triage_real: {df.shape}")
    print(f"triage distribution: {dict(Counter(df['triage_real']))}")

    if len(df) < 10:
        raise SystemExit("dataset demasiado pequeno para baseline")

    X_text, X_ent = build_features(df)
    y = np.asarray(df["triage_real"])

    candidates = {
        "logreg_balanced": LogisticRegression(class_weight="balanced", max_iter=1000, n_jobs=-1),
        "random_forest_balanced": RandomForestClassifier(class_weight="balanced", n_estimators=200, n_jobs=-1, random_state=42),
        "gradient_boosting": GradientBoostingClassifier(random_state=42),
    }

    results = []
    for name, model in candidates.items():
        print(f"\n=== {name} ===")
        try:
            r = evaluate_model(name, model, X_text, X_ent, y)
            print(f"  CV f1_macro     : {r['cv_f1_macro_mean']:.3f} (+/- {r['cv_f1_macro_std']:.3f})")
            print(f"  CV recall_macro : {r['cv_recall_macro_mean']:.3f}")
            print(f"  Recall per class: " + ", ".join(f"{k}={v:.2f}" for k, v in r["train_recall_by_class"].items()))
            results.append(r)
        except Exception as exc:
            print(f"  FAIL: {exc}")
            results.append({"model": name, "error": str(exc)})

    with open(args.out, "w") as f:
        json.dump({"rows": len(df), "results": results}, f, indent=2)
    print(f"\nmetrics written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
