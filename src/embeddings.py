"""
Text embeddings of company business descriptions.

Used to rank candidate peers by how similar their actual
business is, rather than only by Yahoo's industry label.

Model: sentence-transformers/all-MiniLM-L6-v2 (small, free,
runs locally on CPU or GPU) loaded through `transformers` with
mean pooling, so no extra dependency is needed.
"""

import numpy as np

from src.cache import DAY, cached


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_MODEL = None


def _load():

    global _MODEL

    if _MODEL is None:

        import torch
        from transformers import AutoModel, AutoTokenizer

        device = "cuda" if torch.cuda.is_available() else "cpu"

        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()

        _MODEL = (tokenizer, model, device)

    return _MODEL


@cached("embedding", 90 * DAY)
def embed_text(text):
    """Unit-length embedding vector for one text."""

    import torch

    tokenizer, model, device = _load()

    encoded = tokenizer(
        [text], padding=True, truncation=True,
        max_length=256, return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        output = model(**encoded).last_hidden_state

    mask = encoded["attention_mask"].unsqueeze(-1).float()

    vector = (output * mask).sum(1) / mask.sum(1)

    vector = torch.nn.functional.normalize(vector, dim=1)

    return vector[0].cpu().numpy()


def similarity_to(target_text, texts):
    """
    Cosine similarity of each text to the target text.
    Missing texts get NaN.
    """

    def usable(text):
        return isinstance(text, str) and text.strip() != ""

    if not usable(target_text):
        return np.full(len(texts), np.nan)

    target = embed_text(target_text)

    return np.array([
        float(np.dot(target, embed_text(text))) if usable(text) else np.nan
        for text in texts
    ])
