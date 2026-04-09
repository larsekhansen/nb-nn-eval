"""
BLEU + chrF scoring via sacrebleu.

sacrebleu is the standard for reproducible MT scoring — it does its own
tokenization so scores are comparable across papers. We report both
sentence-level BLEU (per segment) and corpus-level BLEU (over all
segments).

chrF is reported alongside BLEU because it's more robust for
morphologically rich languages like Norwegian — small word-ending
changes (which dominate nb↔nn differences) hurt BLEU but are captured
by chrF's character n-grams.
"""
from typing import List

import sacrebleu


def sentence_scores(hypothesis: str, reference: str) -> dict:
    """Score one (hypothesis, reference) pair."""
    bleu = sacrebleu.sentence_bleu(hypothesis, [reference])
    chrf = sacrebleu.sentence_chrf(hypothesis, [reference])
    return {
        "bleu": round(bleu.score, 2),
        "chrf": round(chrf.score, 2),
    }


def corpus_scores(hypotheses: List[str], references: List[str]) -> dict:
    """Score a whole parallel corpus."""
    if len(hypotheses) != len(references):
        raise ValueError(
            f"mismatch: {len(hypotheses)} hypotheses vs {len(references)} references"
        )
    # sacrebleu wants references as list-of-lists (one list per reference set).
    bleu = sacrebleu.corpus_bleu(hypotheses, [references])
    chrf = sacrebleu.corpus_chrf(hypotheses, [references])
    return {
        "bleu": round(bleu.score, 2),
        "chrf": round(chrf.score, 2),
        "n": len(hypotheses),
    }
