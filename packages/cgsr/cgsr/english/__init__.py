"""English-first canonical CGSR components.

The English package is intentionally additive: it does not replace the Korean
CGSR path or the existing RHFC core.  It provides a canonical construction
layer that can be evaluated before any default answer-path integration.
"""

from .canonical_frames import CanonicalAnswerPlan, EnglishConstructionFrame, RealizedAnswer
from .construction_patterns import core_english_frames
from .realizer import realize_answer_plan

__all__ = [
    "CanonicalAnswerPlan",
    "EnglishConstructionFrame",
    "RealizedAnswer",
    "core_english_frames",
    "realize_answer_plan",
]
