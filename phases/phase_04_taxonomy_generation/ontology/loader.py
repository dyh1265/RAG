"""Load classification taxonomy from RDF/Turtle files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from shared.config import get_settings

TAXONOMY_NS = "http://rag.example/taxonomy#"


@dataclass
class Taxonomy:
    """Allowed and forbidden classification labels."""

    allowed_labels: list[str] = field(default_factory=list)
    forbidden_labels: list[str] = field(default_factory=list)
    source_path: str | None = None


def load_taxonomy(path: Path | None = None) -> Taxonomy:
    """Parse classification.ttl (or custom path) into label lists."""
    try:
        from rdflib import Graph, Namespace
        from rdflib.namespace import RDF, RDFS
    except ImportError as exc:
        raise ImportError("Install rdflib: pip install -e '.[phase4]'") from exc

    settings = get_settings()
    ttl_path = path or Path(settings.taxonomies_dir) / "classification.ttl"
    if not ttl_path.exists():
        raise FileNotFoundError(f"Taxonomy not found: {ttl_path}")

    ex = Namespace(TAXONOMY_NS)
    graph = Graph()
    graph.parse(ttl_path, format="turtle")

    def _labels_for(rdf_type) -> list[str]:
        labels: list[str] = []
        for subj, _, _ in graph.triples((None, RDF.type, rdf_type)):
            label = graph.value(subj, RDFS.label)
            if label:
                labels.append(str(label))
            else:
                labels.append(subj.split("#")[-1].replace("-", " "))
        return labels

    return Taxonomy(
        allowed_labels=sorted(set(_labels_for(ex.ClassificationLabel))),
        forbidden_labels=sorted(set(_labels_for(ex.ForbiddenLabel))),
        source_path=str(ttl_path),
    )
