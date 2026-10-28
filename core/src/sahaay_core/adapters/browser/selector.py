"""Semantic Element Selector and Action Grounder for Sahaay Browser Automation.

Derived from Mind2Web research:
- Replaces brittle coordinate and positional heuristics with accessible semantic matching.
- Prioritizes ARIA labels, semantic roles, field names, IDs, placeholders, and visible text.
- Supports bounded few-shot action retrieval for the Muse Spark planner.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("sahaay.adapters.browser.selector")


@dataclass
class ScoredElement:
    """Represents a scored DOM / accessibility candidate element."""

    element_id: str
    score: float
    matched_property: str
    element_role: str
    element_text: str
    attributes: Dict[str, Any]


class SemanticElementSelector:
    """Selects the best matching interactive control from a page observation based on user intent."""

    # Weights assigned to different accessibility & DOM attributes
    WEIGHTS = {
        "aria_label": 1.0,
        "name": 0.90,
        "id": 0.85,
        "placeholder": 0.80,
        "text": 0.75,
        "role_compat": 0.60,
        "testid": 0.70,
    }

    ACTION_ROLE_AFFINITY = {
        "CLICK": {"button", "link", "checkbox", "radio", "switch", "menuitem", "tab"},
        "TYPE": {"textbox", "searchbox", "input", "textarea", "combobox"},
        "SELECT": {"combobox", "listbox", "select", "radio"},
        "SCROLL": {"document", "window", "pane"},
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = weights or self.WEIGHTS

    def _tokenize(self, text: str) -> set[str]:
        """Normalize and tokenize text into lowercase word stems."""
        if not text:
            return set()
        words = re.findall(r"[a-z0-9]+", str(text).lower())
        stopwords = {"the", "a", "an", "to", "in", "for", "on", "of", "and", "or", "by", "from", "with", "is", "at"}
        return {w for w in words if w not in stopwords}

    def _token_jaccard_similarity(self, set_a: set[str], set_b: set[str]) -> float:
        """Calculate Jaccard token overlap between two sets of tokens."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def score_element(
        self, intent: str, element: Dict[str, Any], action_hint: Optional[str] = None
    ) -> ScoredElement:
        """Score an individual candidate element against a user intent."""
        intent_tokens = self._tokenize(intent)
        elem_id = str(element.get("id") or element.get("targetId") or "")
        aria_label = str(element.get("ariaLabel") or element.get("aria-label") or "")
        name = str(element.get("name") or "")
        placeholder = str(element.get("placeholder") or "")
        text = str(element.get("text") or element.get("innerText") or "")
        role = str(element.get("role") or element.get("tagName") or "").lower()
        testid = str(element.get("dataTestId") or element.get("data-testid") or "")

        scores: List[Tuple[str, float]] = []

        # 1. ARIA Label (highest semantic value)
        if aria_label:
            sim = self._token_jaccard_similarity(intent_tokens, self._tokenize(aria_label))
            # Substring bonus
            if any(token in aria_label.lower() for token in intent_tokens if len(token) > 3):
                sim = max(sim, 0.75)
            scores.append(("aria_label", sim * self.weights["aria_label"]))

        # 2. Field Name
        if name:
            sim = self._token_jaccard_similarity(intent_tokens, self._tokenize(name))
            if any(token in name.lower() for token in intent_tokens if len(token) > 3):
                sim = max(sim, 0.65)
            scores.append(("name", sim * self.weights["name"]))

        # 3. Element ID
        if elem_id:
            sim = self._token_jaccard_similarity(intent_tokens, self._tokenize(elem_id))
            if any(token in elem_id.lower() for token in intent_tokens if len(token) > 3):
                sim = max(sim, 0.60)
            scores.append(("id", sim * self.weights["id"]))

        # 4. Placeholder
        if placeholder:
            sim = self._token_jaccard_similarity(intent_tokens, self._tokenize(placeholder))
            scores.append(("placeholder", sim * self.weights["placeholder"]))

        # 5. Visible Text
        if text:
            sim = self._token_jaccard_similarity(intent_tokens, self._tokenize(text))
            if any(token in text.lower() for token in intent_tokens if len(token) > 3):
                sim = max(sim, 0.55)
            scores.append(("text", sim * self.weights["text"]))

        # 6. Test ID
        if testid:
            sim = self._token_jaccard_similarity(intent_tokens, self._tokenize(testid))
            scores.append(("testid", sim * self.weights["testid"]))

        # Pick the best semantic match attribute
        if scores:
            best_prop, best_score = max(scores, key=lambda x: x[1])
        else:
            best_prop, best_score = "none", 0.0

        # Action-role affinity bonus / penalty
        if action_hint and action_hint.upper() in self.ACTION_ROLE_AFFINITY:
            compatible_roles = self.ACTION_ROLE_AFFINITY[action_hint.upper()]
            if role in compatible_roles or any(r in role for r in compatible_roles):
                best_score += 0.20
            else:
                best_score = max(0.0, best_score - 0.25)

        return ScoredElement(
            element_id=elem_id,
            score=round(best_score, 4),
            matched_property=best_prop,
            element_role=role,
            element_text=text or aria_label,
            attributes=element,
        )

    def select_best_target(
        self,
        intent: str,
        candidates: List[Dict[str, Any]],
        action_hint: Optional[str] = None,
        min_threshold: float = 0.20,
    ) -> Optional[ScoredElement]:
        """Rank candidates and return the top match above the confidence threshold."""
        if not candidates:
            return None

        scored = [self.score_element(intent, elem, action_hint=action_hint) for elem in candidates]
        scored.sort(key=lambda s: s.score, reverse=True)

        if scored and scored[0].score >= min_threshold:
            return scored[0]
        return None

    def rank_candidates(
        self, intent: str, candidates: List[Dict[str, Any]], action_hint: Optional[str] = None
    ) -> List[ScoredElement]:
        """Return all candidates sorted by semantic match score."""
        scored = [self.score_element(intent, elem, action_hint=action_hint) for elem in candidates]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored


class FewShotActionRetriever:
    """Bounded in-memory retriever for relevant browser action demonstrations.
    
    Provides sanitized examples to the planner without unverified live web scraping.
    """

    def __init__(self, sample_tasks: Optional[List[Dict[str, Any]]] = None) -> None:
        self.sample_tasks: List[Dict[str, Any]] = sample_tasks or []

    def retrieve_relevant_examples(self, intent: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Retrieve the top-k most relevant sanitized action demonstrations."""
        if not self.sample_tasks:
            return []

        def _intent_similarity(t: Dict[str, Any]) -> float:
            words_a = set(re.findall(r"[a-z0-9]+", intent.lower()))
            words_b = set(re.findall(r"[a-z0-9]+", t.get("userIntent", "").lower()))
            if not words_a or not words_b:
                return 0.0
            return len(words_a & words_b) / len(words_a | words_b)

        scored = [(t, _intent_similarity(t)) for t in self.sample_tasks]
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for task, sim in scored[:top_k]:
            if sim > 0.10:  # Only include if there is meaningful overlap
                results.append({
                    "intent": task.get("userIntent"),
                    "recommendedAction": task.get("groundTruthAction"),
                    "targetRole": task.get("expectedRole"),
                    "similarity": round(sim, 3),
                })
        return results

    def format_examples_for_planner(self, intent: str, top_k: int = 2) -> Optional[str]:
        """Format retrieved examples into a bounded prompt context block."""
        examples = self.retrieve_relevant_examples(intent, top_k=top_k)
        if not examples:
            return None

        lines = ["Relevant verified action patterns:"]
        for idx, ex in enumerate(examples, start=1):
            lines.append(
                f"  [{idx}] When intent is '{ex['intent']}', standard action is {ex['recommendedAction']} on <{ex['targetRole']}> control."
            )
        return "\n".join(lines)
