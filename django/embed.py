# embed_stocks.py
import os
import numpy as np
import torch
import django
from sentence_transformers import SentenceTransformer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from server.models import Stock

_model: SentenceTransformer | None = None


def load_model(model_name: str = "LaBSE") -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name, device="cpu")
        print(f"Loaded model '{model_name}' on CPU")
    return _model


def embed(text: str, model_name: str = "LaBSE") -> np.ndarray:
    model = load_model(model_name)
    emb = model.encode(text, convert_to_numpy=True)
    return emb / np.linalg.norm(emb)


def run():
    stocks = Stock.objects.filter(
        description__isnull=False, embedding__isnull=True
    ).exclude(description="")

    total = stocks.count()
    print(f"Embedding {total} stocks...")

    for i, stock in enumerate(stocks.iterator()):
        try:
            stock.embedding = embed(stock.description).tolist()
            stock.save(update_fields=["embedding"])
            print(f"[{i+1}/{total}] {stock.ticker}")
        except Exception as e:
            print(f"[{i+1}/{total}] {stock.ticker} FAILED: {e}")


if __name__ == "__main__":
    run()
