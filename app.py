from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from policylens.checklist import ChecklistService
from policylens.config import settings
from policylens.coverage import CoverageService
from policylens.database import Database
from policylens.evaluation import evaluate_retrieval, ingest_sample_documents
from policylens.ingestion import IngestionService
from policylens.rag import RAGService
from policylens.vector_store import ChromaVectorStore

st.set_page_config(page_title="PolicyLens | Insurance Policy Assistant", page_icon="🛡️", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1240px;}
      .hero {padding: 1.35rem 1.5rem; border: 1px solid rgba(128,128,128,.25); border-radius: 16px; margin-bottom: 1rem;}
      .muted {opacity: .72; font-size: .9rem;}
      div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.2); padding: .85rem; border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource

def get_services() -> tuple[Database, ChromaVectorStore, IngestionService]:
    database = Database()
    vector_store = ChromaVectorStore()
    return database, vector_store, IngestionService(database, vector_store)


def display_citations(citations: list[dict[str, Any]], title: str = "Sources and supporting passages") -> None:
    if not citations:
        st.caption("No validated source citations were returned for this response.")
        return
    with st.expander(f"{title} · {len(citations)} source(s)", expanded=False):
        for index, citation in enumerate(citations, start=1):
            st.markdown(
                f"**[{index}] {citation.get('source', 'Uploaded document')}**  "
                f"· Page {citation.get('page_number', 'Unknown')} · "
                f"{citation.get('clause_type', 'policy text').replace('_', ' ').title()}"
            )
            st.write(citation.get("passage", ""))
            st.divider()


def render_saved_message(message: dict[str, Any]) -> None:
    role = message["role"] if message["role"] in {"user", "assistant"} else "assistant"
    with st.chat_message(role):
        st.markdown(message["content"])
        if role == "assistant":
            display_citations(message.get("metadata", {}).get("citations", []), "Evidence cited")
            if message.get("metadata", {}).get("has_sufficient_evidence") is False:
                st.caption("PolicyLens marked this response as insufficiently supported by the uploaded evidence.")


def show_result_citations(result: dict[str, Any]) -> None:
    display_citations(result.get("citations", []))


db, vector_store, ingestion = get_services()

st.markdown(
    """<div class="hero">
      <div style="font-size: .82rem; letter-spacing: .12em; text-transform: uppercase; opacity: .72;">Evidence-grounded insurance assistant</div>
      <h1 style="margin: .25rem 0 .4rem 0;">🛡️ PolicyLens</h1>
      <div class="muted">Understand motor policy wording, exclusions, deductibles and claim requirements—with page-level source references.</div>
    </div>""",
    unsafe_allow_html=True,
)

# Sidebar: ingestion, policy workspace and sessions.
with st.sidebar:
    st.header("Policy workspace")
    existing_groups = db.list_policy_groups()
    default_group = "My Motor Policy"
    if "upload_policy_group" not in st.session_state:
        st.session_state.upload_policy_group = default_group
    with st.expander("Add policy PDFs", expanded=not bool(existing_groups)):
        upload_group = st.text_input("Policy / workspace name", key="upload_policy_group")
        upload_type = st.selectbox(
            "Document type",
            ["policy_wording", "policy_schedule", "add_on", "claim_guide", "other"],
            format_func=lambda value: value.replace("_", " ").title(),
        )
        uploaded_files = st.file_uploader(
            "Choose PDF files", type=["pdf"], accept_multiple_files=True,
            help=f"Up to {settings.max_upload_mb} MB per file. Text-based PDFs only; scanned PDFs need OCR first.",
        )
        if st.button("Process uploaded PDFs", type="primary", use_container_width=True):
            if not uploaded_files:
                st.warning("Choose at least one PDF first.")
            elif not upload_group.strip():
                st.warning("Enter a workspace name first.")
            else:
                successes = 0
                for uploaded in uploaded_files:
                    try:
                        record = ingestion.add_pdf(
                            filename=uploaded.name,
                            file_bytes=uploaded.getvalue(),
                            policy_group=upload_group,
                            document_type=upload_type,
                        )
                        st.success(
                            f"Indexed {record['filename']} · {record['page_count']} pages · {record['chunk_count']} chunks"
                        )
                        successes += 1
                    except Exception as exc:
                        st.error(f"{uploaded.name}: {exc}")
                if successes:
                    st.rerun()

    all_groups = db.list_policy_groups()
    if not all_groups:
        all_groups = [default_group]
    if "selected_policy_group" not in st.session_state or st.session_state.selected_policy_group not in all_groups:
        st.session_state.selected_policy_group = all_groups[0]
    policy_group = st.selectbox("Active policy", all_groups, key="selected_policy_group")

    st.divider()
    st.subheader("Documents in this workspace")
    docs = db.list_documents(policy_group)
    if not docs:
        st.caption("No documents indexed yet. Upload a PDF above or load the included synthetic sample documents from the Evaluation tab.")
    for doc in docs:
        with st.container(border=True):
            st.markdown(f"**{doc['filename']}**")
            st.caption(
                f"{doc['document_type'].replace('_', ' ').title()} · {doc['page_count']} pages · {doc['chunk_count']} chunks"
            )
            if st.button("Delete document", key=f"delete_{doc['document_id']}", use_container_width=True):
                ingestion.delete_pdf(doc["document_id"])
                st.success("Document and its indexed chunks were deleted.")
                st.rerun()

    st.divider()
    st.subheader("Conversation history")
    sessions = db.list_sessions(policy_group)
    if not sessions:
        new_id = db.create_session(policy_group)
        sessions = db.list_sessions(policy_group)
        st.session_state.active_session_id = new_id
    session_ids = [item["session_id"] for item in sessions]
    if st.session_state.get("active_session_policy") != policy_group:
        st.session_state.active_session_policy = policy_group
        st.session_state.active_session_id = session_ids[0]
        st.session_state.session_selector = session_ids[0]
    if st.session_state.get("active_session_id") not in session_ids:
        st.session_state.active_session_id = session_ids[0]
    if st.session_state.get("session_selector") not in session_ids:
        st.session_state.session_selector = st.session_state.active_session_id
    session_labels = {item["session_id"]: item["title"] for item in sessions}
    if st.button("＋ New conversation", use_container_width=True):
        new_id = db.create_session(policy_group)
        st.session_state.active_session_id = new_id
        st.session_state.session_selector = new_id
        st.rerun()
    selected_session_id = st.selectbox(
        "Saved conversation", session_ids,
        index=session_ids.index(st.session_state.active_session_id),
        format_func=lambda session_id: session_labels.get(session_id, "Conversation"),
        key="session_selector",
    )
    st.session_state.active_session_id = selected_session_id

    st.divider()
    st.caption("Privacy: uploaded files, Chroma vectors and chat history are stored locally. Retrieved excerpts are sent to the configured Gemini API when you ask for AI analysis.")

active_session_id = st.session_state.active_session_id

# Small dashboard summary.
current_docs = db.list_documents(policy_group)
metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Indexed documents", len(current_docs))
metric_b.metric("Indexed chunks", sum(doc["chunk_count"] for doc in current_docs))
metric_c.metric("Current workspace", policy_group)

tab_ask, tab_coverage, tab_checklist, tab_eval = st.tabs(
    ["💬 Ask your policy", "🔍 Coverage & exclusions", "📋 Claim checklist", "🧪 Evaluation"]
)

with tab_ask:
    st.subheader("Ask a question about your uploaded policy")
    st.caption("Answers are based on the selected workspace. Each displayed citation points to a source PDF and extracted page.")
    history = db.get_messages(active_session_id)
    if not history:
        st.info("Try: ‘Is accidental damage covered?’, ‘What is my compulsory deductible?’, or ‘Does my policy include roadside assistance?’")
    for message in history:
        render_saved_message(message)

    user_question = st.chat_input("Ask about coverage, exclusions, deductibles or claims…")
    if user_question:
        previous_history = db.get_messages(active_session_id, limit=8)
        db.save_message(active_session_id, "user", user_question)
        with st.spinner("Searching policy clauses and preparing an evidence-grounded answer…"):
            try:
                answer_result = RAGService().ask(user_question, policy_group, previous_history)
                db.save_message(
                    active_session_id,
                    "assistant",
                    answer_result["answer"],
                    {
                        "citations": answer_result["citations"],
                        "has_sufficient_evidence": answer_result["has_sufficient_evidence"],
                        "uncertainty": answer_result.get("uncertainty"),
                    },
                )
            except Exception as exc:
                db.save_message(
                    active_session_id, "assistant",
                    f"I couldn't complete the answer because of an application or model error: {exc}",
                    {"citations": [], "has_sufficient_evidence": False},
                )
        st.rerun()

with tab_coverage:
    st.subheader("Coverage and exclusion analysis")
    st.write("Compare potentially relevant benefits with exclusions, conditions, limits and deductibles. This is an explanation of policy wording—not a claim approval decision.")
    with st.form("coverage_form"):
        scenario = st.text_area(
            "Describe the incident or coverage question",
            placeholder="Example: My car was damaged by flooding while parked. What does the uploaded policy say?",
            height=110,
        )
        submitted = st.form_submit_button("Analyse policy evidence", type="primary")
    if submitted:
        with st.spinner("Retrieving coverage, exclusion, condition and deductible clauses…"):
            try:
                result = CoverageService().analyze(scenario, policy_group)
                if result.get("message"):
                    st.warning(result["message"])
                else:
                    analysis = result["analysis"]
                    coverage_history_text = (
                        f"**Potential coverage**\n\n{analysis.coverage_summary}\n\n"
                        f"**Relevant exclusions**\n\n{analysis.relevant_exclusions}\n\n"
                        f"**Conditions and limits**\n\n{analysis.conditions_and_limits}\n\n"
                        f"**Deductible / excess**\n\n{analysis.deductible_or_excess}\n\n"
                        f"**Practical interpretation**\n\n{analysis.practical_interpretation}"
                    )
                    db.save_message(active_session_id, "user", f"Coverage analysis request: {scenario}")
                    db.save_message(active_session_id, "assistant", coverage_history_text, {
                        "citations": result["citations"],
                        "has_sufficient_evidence": not analysis.insufficient_evidence,
                        "analysis_type": "coverage_analysis",
                    })
                    st.markdown("#### What the documents say")
                    st.markdown(f"**Potential coverage**\n\n{analysis.coverage_summary}")
                    st.markdown(f"**Relevant exclusions**\n\n{analysis.relevant_exclusions}")
                    st.markdown(f"**Conditions and limits**\n\n{analysis.conditions_and_limits}")
                    st.markdown(f"**Deductible / excess**\n\n{analysis.deductible_or_excess}")
                    st.markdown(f"**Practical interpretation**\n\n{analysis.practical_interpretation}")
                    if analysis.insufficient_evidence:
                        st.warning("The retrieved documents do not establish a complete coverage decision.")
                    if analysis.missing_information:
                        st.markdown("**Information still needed**")
                        for item in analysis.missing_information:
                            st.write(f"• {item}")
                    show_result_citations(result)
                    st.caption("A claim decision also depends on the complete contract, facts, survey findings and insurer assessment. Confirm ambiguous cases with the insurer.")
            except Exception as exc:
                st.error(f"Coverage analysis failed: {exc}")

with tab_checklist:
    st.subheader("Claim document checklist")
    st.write("PolicyLens extracts documents stated in the uploaded claim procedure. Items are marked required or conditional only when the retrieved wording supports that classification.")
    with st.form("checklist_form"):
        incident = st.text_area(
            "What happened? (helps identify conditional documents)",
            placeholder="Example: Accident damage to the front bumper; no third party involved.",
            height=90,
        )
        checklist_submitted = st.form_submit_button("Generate checklist", type="primary")
    if checklist_submitted:
        with st.spinner("Reading claim procedure and document requirements…"):
            try:
                result = ChecklistService().generate(incident, policy_group)
                if result.get("message"):
                    st.warning(result["message"])
                else:
                    checklist = result["checklist"]
                    checklist_history_text = checklist.summary + "\n\n" + "\n".join(
                        f"- {item.document_name} ({item.requirement_level}): {item.purpose}"
                        for item in checklist.items
                    )
                    db.save_message(active_session_id, "user", f"Claim checklist request: {incident or 'General claim document checklist'}")
                    db.save_message(active_session_id, "assistant", checklist_history_text, {
                        "citations": result["citations"],
                        "has_sufficient_evidence": bool(checklist.items),
                        "analysis_type": "claim_checklist",
                    })
                    st.write(checklist.summary)
                    if checklist.items:
                        st.markdown("#### Documents mentioned by your policy documents")
                        citation_by_id = {source["chunk_id"]: source for source in result["citations"]}
                        for index, item in enumerate(checklist.items):
                            label = f"{item.document_name} — {item.requirement_level.replace('_', ' ').title()}"
                            st.checkbox(label, key=f"check_{active_session_id}_{index}")
                            st.caption(item.purpose + (f" When needed: {item.when_needed}" if item.when_needed else ""))
                            item_sources = [citation_by_id[cid] for cid in item.evidence_ids if cid in citation_by_id]
                            if item_sources:
                                source_labels = ", ".join(
                                    f"{src['source']} p.{src['page_number']}" for src in item_sources
                                )
                                st.caption(f"Evidence: {source_labels}")
                    else:
                        st.info("No individual documents were explicitly identified in the retrieved excerpts.")
                    if checklist.missing_user_information:
                        st.markdown("**Please clarify**")
                        for item in checklist.missing_user_information:
                            st.write(f"• {item}")
                    show_result_citations(result)
                    st.caption("This checklist is a starting point, not a guarantee that the insurer will not request additional documents.")
            except Exception as exc:
                st.error(f"Checklist generation failed: {exc}")

with tab_eval:
    st.subheader("Evaluate retrieval quality")
    st.write("The included benchmark uses manually selected evidence phrases from synthetic sample policies. It measures retrieval precision/recall and checks that selected absent topics do not have their gold phrases in retrieved chunks.")
    st.info("Answer faithfulness, answer relevance, final citation correctness and live-model latency need separate answer-level runs and human review; the retrieval-only benchmark does not claim to measure them.")
    if st.button("Load synthetic sample policies and run evaluation", type="primary"):
        try:
            with st.spinner("Indexing sample PDFs and running the local retrieval benchmark. The embedding model may download on first use…"):
                ingest_sample_documents()
                report = evaluate_retrieval(settings.root_dir / "evaluation" / "gold_questions.json")
            report_path = settings.root_dir / "evaluation" / "latest_results.json"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            st.session_state.latest_eval_report = report
            st.success(f"Evaluation finished. Results saved to {report_path.relative_to(settings.root_dir)}")
        except Exception as exc:
            st.error(f"Evaluation failed: {exc}")
    if st.session_state.get("latest_eval_report"):
        report = st.session_state.latest_eval_report
        c1, c2, c3 = st.columns(3)
        c1.metric("Precision@k", report.get("retrieval_precision_at_k_mean") or "N/A")
        c2.metric("Recall@k", report.get("retrieval_recall_at_k_mean") or "N/A")
        c3.metric("Absent-evidence checks", f"{report['absent_evidence_checks_passed']}/{report['absent_evidence_checks_total']}")
        st.dataframe(report["per_question"], use_container_width=True, hide_index=True)

st.divider()
st.caption("PolicyLens is a portfolio/demo application using synthetic sample documents. It is not an insurer, broker, legal adviser or claim adjudicator. Do not use it as the sole basis for insurance or financial decisions.")
