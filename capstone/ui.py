"""
DocuMind Streamlit UI — upload PDF, chat with citations.

Run:
    pip install streamlit
    streamlit run capstone/ui.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from capstone.pipeline import DocuMind, DocuMindConfig


st.set_page_config(page_title="DocuMind", page_icon="📄", layout="wide")
st.title("DocuMind")
st.caption("Capstone — multimodal RAG with taxonomy conformity")

api_url = st.sidebar.text_input("API URL (optional)", placeholder="http://localhost:8002")
text_only = st.sidebar.checkbox("Text-only mode", value=True)
provider = st.sidebar.selectbox("LLM provider", ["openai", "ollama"])

cfg = DocuMindConfig.from_settings()
cfg.text_only = text_only
cfg.llm_provider = provider
dm = DocuMind(cfg, api_url=api_url or None)

if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

uploaded = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded is not None:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = Path(tmp.name)
    with st.spinner("Ingesting…"):
        result = dm.ingest(tmp_path)
    st.session_state.doc_id = result.doc_id
    st.success(f"Ingested {result.chunk_count} chunks · doc_id={result.doc_id}")

if st.session_state.doc_id:
    st.info(f"Active doc_id: `{st.session_state.doc_id}`")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("conformity"):
            st.warning(msg["conformity"])

if prompt := st.chat_input("Ask about the document…"):
    if not st.session_state.doc_id:
        st.error("Upload a PDF first.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            response = dm.ask(
                prompt,
                doc_id=st.session_state.doc_id,
                provider=provider,
            )
        st.markdown(response.answer or "_(no answer)_")

        conformity = response.metadata.get("conformity")
        if conformity and conformity.get("flagged"):
            reason = conformity.get("reason") or "Taxonomy violation"
            st.warning(f"Conformity flagged: {reason}")
            st.session_state.messages.append(
                {"role": "assistant", "content": response.answer or "", "conformity": reason}
            )
        else:
            st.session_state.messages.append(
                {"role": "assistant", "content": response.answer or ""}
            )

        if response.citations:
            with st.expander("Citations"):
                for idx, cite in enumerate(response.citations, start=1):
                    st.markdown(f"**[{idx}]** page {cite.page_number} — {cite.excerpt[:200]}")
