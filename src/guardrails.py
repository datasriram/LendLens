from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    blocked: bool
    reason: str | None = None
    message: str | None = None


LOAN_DECISION_PATTERNS = [
    r"\b(approve|approved|approving|reject|rejected|rejecting|deny|denied|denying|sanction|sanctioned|sanctioning|grant|granted|granting)\b.{0,60}\b(loan|application|borrower|customer)\b",
    r"\b(loan|application|borrower|customer)\b.{0,60}\b(approve|approved|approving|reject|rejected|rejecting|deny|denied|denying|sanction|sanctioned|sanctioning|grant|granted|granting)\b",
]


def check_query(question: str) -> GuardrailResult:

    q = question.lower().strip()

    for pattern in LOAN_DECISION_PATTERNS:

        if re.search(
            pattern,
            q,
            flags=re.IGNORECASE,
        ):
            return GuardrailResult(
                blocked=True,
                reason="automated_lending_decision",
                message=(
                    "LendLens does not make or recommend "
                    "individual loan approval or rejection decisions."
                ),
            )

    return GuardrailResult(
        blocked=False
    )
