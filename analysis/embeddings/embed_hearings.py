# embed_hearings.py
import json
import numpy as np
import torch
from sentence_transformers import SentenceTransformer


def get_device() -> str:
    if torch.backends.mps.is_available():
        print("Using MPS (Apple Silicon)")
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


_model: SentenceTransformer | None = None


def load_model(model_name: str = "LaBSE") -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name, device=get_device())
        print(f"Loaded model '{model_name}'")
    return _model


def chunk_text(text: str, max_words: int = 100, overlap: int = 10) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += max_words - overlap
    return chunks


def embed(
    text: str, max_words: int = 100, overlap: int = 10, model_name: str = "LaBSE"
) -> np.ndarray:
    model = load_model(model_name)
    chunks = chunk_text(text, max_words=max_words, overlap=overlap)
    if len(chunks) == 1:
        emb = model.encode(chunks[0], convert_to_numpy=True)
        return emb / np.linalg.norm(emb)
    chunk_embeddings = model.encode(chunks, convert_to_numpy=True)
    weights = np.array([len(c.split()) for c in chunks], dtype=float)
    weights /= weights.sum()
    pooled = np.average(chunk_embeddings, axis=0, weights=weights)
    pooled /= np.linalg.norm(pooled)
    return pooled


def run(
    input_path: str = "../data/hearings_export.json",
    output_path: str = "../data/hearings_embeddings.jsonl",
):
    with open(input_path) as f:
        hearings = json.load(f)

    # Resume support: skip jacket_nos already in output
    done = set()
    if os.path.exists(output_path):
        with open(output_path) as f:
            for line in f:
                done.add(json.loads(line)["jacket_no"])
        print(f"Resuming: {len(done)} already embedded")

    with open(output_path, "a") as f:
        for i, h in enumerate(hearings):
            if h["jacket_no"] in done:
                continue
            try:
                emb = embed(h["transcript"]).tolist()
                f.write(
                    json.dumps({"jacket_no": h["jacket_no"], "embedding": emb}) + "\n"
                )
                f.flush()
                print(f"[{i+1}/{len(hearings)}] {h['jacket_no']}")
            except Exception as e:
                print(f"[{i+1}/{len(hearings)}] {h['jacket_no']} FAILED: {e}")


if __name__ == "__main__":
    import os

    run()
