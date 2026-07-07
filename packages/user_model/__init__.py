"""User deep model — Phase 3-2 (선호·소유·습관, 로컬 전용).

Derives WHO the user is from what actually happened: episodic events + local
brain conversational facts. Every derived statement carries its evidence; an
unknown is reported as unknown, never guessed.
"""

from .model import derive_user_model, summary_facts, user_context_line

__all__ = ["derive_user_model", "summary_facts", "user_context_line"]
