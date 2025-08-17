import os
from typing import Iterable, List, Optional, Tuple

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "text_clf.joblib")


def build_pipeline() -> Pipeline:
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        analyzer="word",
        ngram_range=(1, 3),
        min_df=2,
        max_df=0.9,
    )
    classifier = LogisticRegression(
        max_iter=200,
        n_jobs=None,
        class_weight="balanced",
        solver="lbfgs",
        multi_class="auto",
    )
    pipeline = Pipeline([
        ("tfidf", vectorizer),
        ("clf", classifier),
    ])
    return pipeline


def train_model(texts: Iterable[str], labels: Iterable[str]) -> Tuple[Pipeline, Optional[str]]:
    X = list(texts)
    y = list(labels)
    if len(set(y)) < 2:
        pipe = build_pipeline()
        return pipe.fit(X, y), None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipe = build_pipeline()
    pipe.fit(X_train, y_train)
    try:
        y_pred = pipe.predict(X_test)
        report = classification_report(y_test, y_pred)
    except Exception:
        report = None
    return pipe, report


def predict_categories(pipeline: Pipeline, texts: Iterable[str]) -> List[str]:
    return list(pipeline.predict(list(texts)))


def save_model(pipeline: Pipeline, path: str = MODEL_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(pipeline, path)


def load_model(path: str = MODEL_PATH) -> Optional[Pipeline]:
    if not os.path.exists(path):
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None