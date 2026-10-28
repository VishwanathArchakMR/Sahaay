"""Citation Generator and Conflict Detector for Internet Research."""

from typing import Any, Dict, List

from sahaay_core.research.models import Citation


class CitationEngine:
    """Manages citation rendering, source attribution, and conflict identification."""

    @staticmethod
    def format_citations_markdown(citations: List[Citation]) -> str:
        """Formats citation records as Markdown footnotes."""
        if not citations:
            return ""

        lines = ["\n### Verified Internet Research Sources"]
        for idx, cite in enumerate(citations, 1):
            lines.append(
                f"[{idx}] **{cite.title}**  \n"
                f"    URL: [{cite.url}]({cite.url})  \n"
                f"    Retrieved: {cite.retrieved_at} | Verified Source ID: `{cite.source_id}`"
            )
        return "\n".join(lines)

    @staticmethod
    def detect_conflicts(statements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identifies conflicting factual claims across different source URLs."""
        conflicts = []
        # Key on subject/field to detect numerical or factual divergence
        field_values: Dict[str, List[Dict[str, Any]]] = {}

        for item in statements:
            field = item.get("field")
            if field:
                field_values.setdefault(field, []).append(item)

        for field, occurrences in field_values.items():
            if len(occurrences) > 1:
                unique_vals = {str(o.get("value")).strip().lower() for o in occurrences}
                if len(unique_vals) > 1:
                    conflicts.append(
                        {
                            "field": field,
                            "divergentValues": list(unique_vals),
                            "sources": [o.get("sourceUrl") for o in occurrences],
                        }
                    )
        return conflicts
