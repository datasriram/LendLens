from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import models


@dataclass
class RoutingDecision:
    query_filter: models.Filter | None
    details: dict[str, Any]


PUBLISHER_RULES = {
    "iifl": "IIFL Finance Limited",
    "tata capital": "Tata Capital Limited",
    "bajaj finance": "Bajaj Finance Limited",
    "shriram": "Shriram Finance Limited",
}


CATEGORY_RULES = [
    (
        [
            "customer due diligence",
            " cdd ",
            "kyc",
            "know your customer",
            "aadhaar",
            "ckyc",
            "ckycr",
        ],
        "kyc_aml",
    ),
    (
        [
            "digital lending",
            "lending service provider",
            " lsp ",
            "dla",
        ],
        "digital_lending",
    ),
    (
        [
            "cybersecurity",
            "cyber security",
            "technology risk",
        ],
        "cybersecurity",
    ),
    (
        [
            "fraud risk",
            "fraud management",
        ],
        "fraud_risk",
    ),
    (
        [
            "stressed asset",
            "stressed borrower",
            "stressed loan",
            "stressed account",
            "resolution of stressed",
            "resolution framework",
            "special mention account",
            "sma-0",
            "sma-1",
            "sma-2",
        ],
        "stressed_assets",
    ),
    (
        [
            "credit risk",
        ],
        "credit_risk",
    ),
    (
        [
            "internal ombudsman",
        ],
        "internal_ombudsman",
    ),
    (
        [
            "outsourcing",
            "service provider outsourcing",
        ],
        "outsourcing",
    ),
]


def detect_publisher(
    query: str,
) -> str | None:

    q = query.lower()

    for phrase, publisher in PUBLISHER_RULES.items():

        if phrase in q:
            return publisher

    return None


def detect_category(
    query: str,
) -> str | None:

    q = f" {query.lower()} "

    # Recognize common variations in stressed-account terminology.
    # These rules identify scope; they do not supply answer facts.
    stress_terms = (
        "stress",
        "stressed",
        "resolution",
    )
    account_terms = (
        "borrower",
        "loan",
        "account",
        "asset",
        "overdue",
    )

    if (
        any(term in q for term in stress_terms)
        and any(term in q for term in account_terms)
    ):
        return "stressed_assets"

    for phrases, category in CATEGORY_RULES:

        if any(
            phrase in q
            for phrase in phrases
        ):
            return category

    return None


def route_query(
    query: str,
) -> RoutingDecision:

    q = query.lower()

    must_conditions = []

    details = {
        "publisher": None,
        "authority": None,
        "category": None,
        "temporal_role": None,
    }

    # ------------------------------------------------------
    # Rule 1:
    # Explicit company name = restrict retrieval to company.
    # ------------------------------------------------------

    publisher = detect_publisher(query)

    if publisher:

        must_conditions.append(
            models.FieldCondition(
                key="publisher",
                match=models.MatchValue(
                    value=publisher
                ),
            )
        )

        details["publisher"] = publisher


    # ------------------------------------------------------
    # Rule 2:
    # Regulatory questions can use RBI authority/category.
    #
    # We intentionally DON'T force this when the user has
    # explicitly asked about a company.
    # ------------------------------------------------------

    else:

        category = detect_category(query)

        regulatory_query = (
            "rbi" in q
            or "nbfc" in q
            or category is not None
        )

        if regulatory_query:

            must_conditions.append(
                models.FieldCondition(
                    key="authority",
                    match=models.MatchValue(
                        value="regulator"
                    ),
                )
            )

            details["authority"] = "regulator"

            # Prefer the manually/current verified RBI core.
            must_conditions.append(
                models.FieldCondition(
                    key="temporal_role",
                    match=models.MatchValue(
                        value="current_verified"
                    ),
                )
            )

            details[
                "temporal_role"
            ] = "current_verified"

            if category:

                must_conditions.append(
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(
                            value=category
                        ),
                    )
                )

                details["category"] = category


    if not must_conditions:

        return RoutingDecision(
            query_filter=None,
            details=details,
        )

    return RoutingDecision(
        query_filter=models.Filter(
            must=must_conditions
        ),
        details=details,
    )
