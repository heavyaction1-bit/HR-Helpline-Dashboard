from __future__ import annotations

import os

import streamlit as st

from hr_analytics.ai_insights import ask_openai, build_dashboard_context, context_to_json
from hr_analytics.config import DEFAULT_OPENAI_MODEL
from .components import empty_state


EXAMPLE_QUESTIONS = [
    "What are the main operational pressure points in the current dashboard?",
    "How do sickness and annual leave appear to relate to call handling performance?",
    "Which months should I look at more closely, and why?",
    "Draft a fair, caveated summary of staff workload for this period.",
    "What questions should I take to the next team planning meeting?",
]


def _streamlit_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def render(calls, absence, employees, filters, selected_team: list[str]) -> None:
    st.header("ChatGPT Insights")
    st.caption("Ask questions about the currently scoped and filtered dashboard data.")

    if calls.empty and absence.empty:
        empty_state("Select team members and filters before asking for insights.")
        return

    st.info(
        "Approved AI feature: the app sends the current dashboard context to the OpenAI API when you ask a question. "
        "Use outputs as analytical suggestions, not HR decisions."
    )

    with st.expander("Data sent to ChatGPT", expanded=False):
        include_staff_detail = st.checkbox("Include staff-level metrics", value=True)
        include_case_rows = st.checkbox("Include recent case-level rows", value=False)
        case_row_limit = st.slider("Maximum case rows to include", min_value=25, max_value=500, value=100, step=25)
        st.caption("Aggregated dashboard metrics are always included. Case rows are capped to keep the request practical.")

    api_key = os.getenv("OPENAI_API_KEY") or _streamlit_secret("OPENAI_API_KEY")
    if api_key:
        st.success("Using `OPENAI_API_KEY` from the app environment or Streamlit secrets.")
        temporary_key = ""
    else:
        st.warning("Set `OPENAI_API_KEY` in your environment, or paste a temporary key below for this session.")
        temporary_key = st.text_input("Temporary OpenAI API key", type="password")
    active_key = api_key or temporary_key

    model = st.text_input(
        "Model",
        value=os.getenv("OPENAI_MODEL") or _streamlit_secret("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
    )
    max_output_tokens = st.slider("Response length", min_value=500, max_value=3000, value=1400, step=100)

    context = build_dashboard_context(
        calls,
        absence,
        employees,
        filters,
        selected_team,
        include_staff_detail=include_staff_detail,
        include_case_rows=include_case_rows,
        case_row_limit=case_row_limit,
    )

    with st.expander("Preview context summary", expanded=False):
        st.json(context, expanded=False)

    if "chatgpt_insights_history" not in st.session_state:
        st.session_state["chatgpt_insights_history"] = []

    selected_example = st.selectbox("Example questions", [""] + EXAMPLE_QUESTIONS)
    question = st.text_area(
        "Ask ChatGPT about this dashboard",
        value=selected_example,
        height=120,
        placeholder="Ask about pressure points, staff workload, absence impact, category trends, or what to investigate next.",
    )

    left, right = st.columns([1, 1])
    with left:
        ask_button = st.button("Ask ChatGPT", type="primary", disabled=not bool(active_key and question.strip()))
    with right:
        if st.button("Clear insight history"):
            st.session_state["chatgpt_insights_history"] = []
            st.rerun()

    if ask_button:
        with st.spinner("Asking ChatGPT about the current dashboard context..."):
            try:
                answer = ask_openai(
                    api_key=active_key,
                    model=model.strip() or DEFAULT_OPENAI_MODEL,
                    question=question.strip(),
                    context=context,
                    max_output_tokens=max_output_tokens,
                )
            except Exception as exc:
                st.error(f"OpenAI request failed: {exc}")
            else:
                st.session_state["chatgpt_insights_history"].insert(
                    0,
                    {
                        "question": question.strip(),
                        "answer": answer,
                        "model": model.strip() or DEFAULT_OPENAI_MODEL,
                    },
                )

    for index, item in enumerate(st.session_state["chatgpt_insights_history"], start=1):
        with st.container(border=True):
            st.markdown(f"**Question {index}:** {item['question']}")
            st.markdown(item["answer"])
            st.caption(f"Model: {item['model']}")
            st.download_button(
                "Download this insight",
                data=f"# ChatGPT dashboard insight\n\n## Question\n{item['question']}\n\n## Answer\n{item['answer']}\n",
                file_name=f"chatgpt_dashboard_insight_{index}.md",
                mime="text/markdown",
                key=f"download_chatgpt_insight_{index}",
            )

    with st.expander("Download current AI context JSON", expanded=False):
        st.download_button(
            "Download context JSON",
            data=context_to_json(context),
            file_name="dashboard_context_for_chatgpt.json",
            mime="application/json",
        )
