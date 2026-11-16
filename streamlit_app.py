from __future__ import annotations

import os
from urllib.parse import urlsplit

import requests
import streamlit as st

API_URL = (os.getenv("LENDLENS_API_URL") or "http://127.0.0.1:8000").rstrip("/")
DEMO_TOKEN = os.getenv("LENDLENS_DEMO_TOKEN", "")
PUBLIC_DEMO = os.getenv("LENDLENS_PUBLIC_DEMO") == "1" or bool(DEMO_TOKEN)


st.set_page_config(
    page_title="LendLens",
    page_icon="🔎",
    layout="wide",
)


if PUBLIC_DEMO:
    endpoint = urlsplit(API_URL)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or not DEMO_TOKEN:
        st.error("The demo backend is not configured.")
        st.stop()

st.title("LendLens")

st.caption(
    "NBFC Regulatory & Policy Intelligence"
)

st.info(
    "Answers are generated only from retrieved "
    "RBI and NBFC public-source evidence."
)


with st.form("question_form"):

    question_text = st.text_area(
        "Ask regulatory or policy questions",
        placeholder=(
            "What documents must an NBFC obtain when performing CDD for an individual?\n"
            "Within how many days should Tata Capital respond to a customer grievance?\n"
            "What is Tata Capital's CEO's favorite food?"
        ),
        height=160,
    )

    submitted = st.form_submit_button(
        "Ask LendLens",
        type="primary",
    )


def ask_api(question: str):

    response = requests.post(
        f"{API_URL}/ask",
        json={
            "question": question
        },
        headers={"Authorization": f"Bearer {DEMO_TOKEN}"} if PUBLIC_DEMO else {},
        timeout=180,
        allow_redirects=False,
    )

    if response.is_redirect:
        raise requests.HTTPError("Unexpected backend redirect", response=response)
    response.raise_for_status()

    return response.json()


def display_result(
    number: int,
    data: dict,
):

    st.markdown("---")

    st.subheader(
        f"Question {number}"
    )

    st.markdown(
        f"**{data.get('question', '')}**"
    )

    st.markdown("### Answer")

    if data.get("abstained"):

        st.warning(
            data.get("answer")
        )

    else:

        st.success(
            data.get("answer")
        )

    st.caption(
        f"Response time: "
        f"{data.get('latency_seconds', '?')} seconds"
    )

    if not PUBLIC_DEMO:
        with st.expander("Retrieval routing"):
            st.json(data.get("routing") or {})

    sources = (
        data.get("sources")
        or []
    )

    if sources:

        st.markdown(
            "### Supporting sources"
        )

        for source in sources:

            source_id = source.get(
                "id",
                "Source",
            )

            title = (
                source.get("title")
                or "Untitled"
            )

            page = source.get(
                "page"
            )

            label = (
                f"[{source_id}] {title}"
            )

            if page is not None:

                label += (
                    f" — Page {page}"
                )

            with st.expander(
                label
            ):

                st.write(
                    "**Publisher:**",
                    source.get(
                        "publisher"
                    ),
                )

                st.write(
                    "**Authority:**",
                    source.get(
                        "authority"
                    ),
                )

                st.write(
                    "**Temporal status:**",
                    source.get(
                        "temporal_role"
                    ),
                )

                st.write(
                    "**Category:**",
                    source.get(
                        "category"
                    ),
                )

                url = source.get(
                    "url"
                )

                if url:

                    st.markdown(
                        f"[Open original source]({url})"
                    )


if submitted:

    questions = [
        line.strip()
        for line in question_text.splitlines()
        if line.strip()
    ]

    if not questions:

        st.warning(
            "Enter at least one question."
        )

    elif PUBLIC_DEMO and (len(questions) > 1 or len(questions[0]) > 1000):

        st.warning("Enter one question of at most 1,000 characters.")

    else:

        st.markdown(
            f"### Processing {len(questions)} question(s)"
        )

        progress = st.progress(0)

        for index, question in enumerate(
            questions,
            start=1,
        ):

            try:

                with st.spinner(
                    f"Processing question "
                    f"{index} of {len(questions)}..."
                ):

                    data = ask_api(
                        question
                    )

                display_result(
                    index,
                    data,
                )

            except requests.RequestException as exc:
                if PUBLIC_DEMO:
                    if exc.response is not None and exc.response.status_code == 429:
                        st.warning("The demo is busy. Please try again shortly.")
                    else:
                        st.error("The demo could not process your question. Please try again later.")
                else:
                    st.error(f"Question {index} failed: {exc}")

            progress.progress(
                index / len(questions)
            )


st.divider()

st.caption(
    "LendLens is an evidence-grounded research "
    "and decision-support system. It does not "
    "provide legal advice or automated lending decisions."
)
