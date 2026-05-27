from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, cross_val_predict
from sklearn.preprocessing import MultiLabelBinarizer

try:
    from triage_common.dictionary import list_clinical_terms
except Exception:
    list_clinical_terms = None


TRIAGE_CLASSES = ["C1", "C2", "C3", "C4", "C5"]
TRIAGE_LEVEL = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}


@dataclass
class TrainedArtifacts:
    estimator_name: str
    pipeline: dict
    metrics: dict


def _ensure_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value)


def _entity_term(value) -> str:
    if isinstance(value, dict):
        return str(value.get("termino_clinico", ""))
    return str(value)


def _ensure_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [t for t in (_entity_term(v) for v in value) if t]
    if isinstance(value, (np.ndarray,)):
        return [t for t in (_entity_term(v) for v in value.tolist()) if t]
    return []


def build_features(df: pd.DataFrame, text_col: str = "resumen_es", entity_col: str = "entidades_normalizadas_es"):
    texts = [_ensure_text(v) for v in df[text_col].tolist()] if text_col in df else [""] * len(df)
    entities = [_ensure_list(v) for v in df[entity_col].tolist()] if entity_col in df else [[]] * len(df)
    return texts, entities


def _candidate_estimators() -> dict[str, ClassifierMixin]:
    return {
        "logistic_regression": LogisticRegression(
            class_weight="balanced", max_iter=1000
        ),
        "random_forest": RandomForestClassifier(
            class_weight="balanced", n_estimators=200, random_state=42, n_jobs=1
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=42, n_estimators=120),
    }


def _load_vocab() -> list[str] | None:
    if list_clinical_terms is None:
        return None
    try:
        terms = list_clinical_terms()
    except Exception:
        return None
    return sorted(terms) if terms else None


def _filter_to_vocab(entities: list[list[str]], vocab: Iterable[str]) -> list[list[str]]:
    allowed = set(vocab)
    return [[e for e in row if e in allowed] for row in entities]


def _make_vectorizers(texts: list[str], entities: list[list[str]], vocab: list[str] | None = None):
    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.95)
    tfidf_matrix = tfidf.fit_transform(texts)
    if vocab is not None:
        mlb = MultiLabelBinarizer(classes=vocab)
        mlb.fit([vocab])
        entity_matrix = mlb.transform(_filter_to_vocab(entities, vocab))
    else:
        mlb = MultiLabelBinarizer()
        entity_matrix = mlb.fit_transform(entities)
    features = hstack([tfidf_matrix, entity_matrix]).tocsr()
    return tfidf, mlb, features


def _transform(tfidf: TfidfVectorizer, mlb: MultiLabelBinarizer, texts: list[str], entities: list[list[str]]):
    tfidf_matrix = tfidf.transform(texts)
    entity_matrix = mlb.transform(_filter_to_vocab(entities, mlb.classes_.tolist()))
    return hstack([tfidf_matrix, entity_matrix]).tocsr()


def _safe_cv(y: np.ndarray) -> int:
    class_counts = pd.Series(y).value_counts()
    if (class_counts < 2).any():
        return 0
    return min(5, int(class_counts.min()))


def _groups_from_df(df: pd.DataFrame) -> np.ndarray | None:
    if "id_caso" not in df.columns:
        return None
    return df["id_caso"].astype(str).apply(lambda s: re.sub(r"_AUG_\d+$", "", s)).to_numpy()


def _under_triage_rate(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    pairs = [
        (TRIAGE_LEVEL[t], TRIAGE_LEVEL[p])
        for t, p in zip(y_true.tolist(), y_pred.tolist())
        if t in TRIAGE_LEVEL and p in TRIAGE_LEVEL
    ]
    if not pairs:
        return 0.0
    return float(np.mean([pred > true for true, pred in pairs]))


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    labels_present = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    report = classification_report(y_true, y_pred, labels=labels_present, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels_present).tolist()
    return {
        "labels": labels_present,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_per_class": {
            cls: float(recall_score(y_true, y_pred, labels=[cls], average="macro", zero_division=0))
            for cls in labels_present
        },
        "under_triage_rate": _under_triage_rate(y_true, y_pred),
        "classification_report": report,
        "confusion_matrix": cm,
    }


def train_best(df: pd.DataFrame) -> TrainedArtifacts:
    if df.empty:
        raise ValueError("Dataset vacio")
    if "triage_real" not in df.columns:
        raise ValueError("Falta columna triage_real")

    texts, entities = build_features(df)
    y = df["triage_real"].astype(str).to_numpy()
    vocab = _load_vocab()
    groups = _groups_from_df(df)

    n_splits = _safe_cv(y)

    results: list[tuple[str, ClassifierMixin, dict]] = []

    for name, estimator in _candidate_estimators().items():
        tfidf, mlb, x = _make_vectorizers(texts, entities, vocab)
        if n_splits >= 2:
            if groups is not None:
                cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
                y_pred = cross_val_predict(estimator, x, y, cv=cv, groups=groups)
            else:
                cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
                y_pred = cross_val_predict(estimator, x, y, cv=cv)
        else:
            estimator.fit(x, y)
            y_pred = estimator.predict(x)
        metrics = _compute_metrics(y, y_pred)
        metrics["cv_splits"] = n_splits
        results.append((name, estimator, metrics))

    results.sort(key=lambda r: r[2]["f1_macro"], reverse=True)
    best_name, best_est, best_metrics = results[0]

    tfidf, mlb, x = _make_vectorizers(texts, entities, vocab)
    best_est.fit(x, y)

    pipeline_payload = {
        "estimator_name": best_name,
        "estimator": best_est,
        "tfidf": tfidf,
        "mlb": mlb,
        "classes": list(best_est.classes_),
    }

    all_metrics = {
        "selected_model": best_name,
        "candidates": {name: m for name, _, m in results},
        "best": best_metrics,
    }

    return TrainedArtifacts(estimator_name=best_name, pipeline=pipeline_payload, metrics=all_metrics)


def predict_triage(pipeline_payload: dict, texto: str, entidades: Iterable[str]) -> tuple[str, dict[str, float]]:
    tfidf = pipeline_payload["tfidf"]
    mlb = pipeline_payload["mlb"]
    estimator = pipeline_payload["estimator"]
    features = _transform(tfidf, mlb, [_ensure_text(texto)], [list(entidades)])

    probs: dict[str, float] = {}
    if hasattr(estimator, "predict_proba"):
        proba = estimator.predict_proba(features)[0]
        for cls, value in zip(estimator.classes_, proba):
            probs[str(cls)] = float(value)
    pred = str(estimator.predict(features)[0])
    return pred, probs
