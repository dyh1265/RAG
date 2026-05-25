"""
Image embedder using OpenCLIP (ViT-B-32 / LAION by default).
Embeds figure PNGs and encodes text queries in the same CLIP space.
"""

from __future__ import annotations

from pathlib import Path

import torch

from shared.config import get_settings
from shared.models import DocumentChunk, EmbeddedChunk

# HuggingFace-style name → (open_clip architecture, pretrained tag)
_OPENCLIP_PRESETS: dict[str, tuple[str, str]] = {
    "laion/CLIP-ViT-B-32-laion2B-s34B-b79K": ("ViT-B-32", "laion2b_s34b_b79k"),
}


class ImageEmbedder:
    """
    Wraps OpenCLIP for figure image embedding and query encoding.

    Install: pip install open_clip_torch Pillow

    Usage
    -----
    embedder = ImageEmbedder()
    vectors = embedder.embed_images(["path/to/figure.png"])
    query_vec = embedder.embed_query("revenue chart trends")
    """

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.image_embedding_model
        self.device = device or settings.embedding_device
        preset = _OPENCLIP_PRESETS.get(self.model_name, ("ViT-B-32", "laion2b_s34b_b79k"))
        self.arch, self.pretrained = preset
        self._model = None
        self._preprocess = None
        self._tokenizer = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import open_clip
        except ImportError:
            raise ImportError("Install open_clip_torch: pip install open_clip_torch")

        model, _, preprocess = open_clip.create_model_and_transforms(
            self.arch,
            pretrained=self.pretrained,
            device=self.device,
        )
        model.eval()
        self._model = model
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer(self.arch)

    def _normalize(self, tensor: torch.Tensor) -> torch.Tensor:
        return tensor / tensor.norm(dim=-1, keepdim=True).clamp(min=1e-12)

    def embed_images(self, image_paths: list[str | Path]) -> list[list[float]]:
        """Embed local image files; returns L2-normalised vectors."""
        from PIL import Image

        self._ensure_loaded()
        tensors = []
        for path in image_paths:
            with Image.open(path).convert("RGB") as img:
                tensors.append(self._preprocess(img).unsqueeze(0))

        batch = torch.cat(tensors, dim=0).to(self.device)
        with torch.no_grad():
            vectors = self._normalize(self._model.encode_image(batch))
        return vectors.cpu().tolist()

    def embed_query(self, text: str) -> list[float]:
        """Encode a text query in CLIP space for searching figure_chunks."""
        self._ensure_loaded()
        tokens = self._tokenizer([text]).to(self.device)
        with torch.no_grad():
            vector = self._normalize(self._model.encode_text(tokens))
        return vector[0].cpu().tolist()

    def embed_figure_chunks(self, chunks: list[DocumentChunk]) -> list[EmbeddedChunk]:
        """Embed figure chunks from their cropped PNG paths."""
        if not chunks:
            return []
        paths = []
        for chunk in chunks:
            if not chunk.image_path:
                raise ValueError(f"Figure chunk {chunk.id} has no image_path")
            paths.append(chunk.image_path)
        vectors = self.embed_images(paths)
        return [
            EmbeddedChunk(chunk=chunk, vector=vec, model_name=self.model_name)
            for chunk, vec in zip(chunks, vectors)
        ]

    @property
    def vector_size(self) -> int:
        self._ensure_loaded()
        return self._model.visual.output_dim
