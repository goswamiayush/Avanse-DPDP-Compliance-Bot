import streamlit as st
import pandas as pd
from src.document_processor import process_uploaded_files
from src.ai_engine import analyze_dpdp_compliance, chat_with_grounding, AVAILABLE_MODELS

def apply_color_coding(val):
    if val == 'Compliant':
        return '<span style="color: #15803d; font-weight: bold; background-color: #dcfce7; padding: 2px 8px; border-radius: 4px;">✅ Compliant</span>'
    elif val == 'Non-Compliant':
        return '<span style="color: #b91c1c; font-weight: bold; background-color: #fee2e2; padding: 2px 8px; border-radius: 4px;">❌ Non-Compliant</span>'
    elif val == 'Missing':
        return '<span style="color: #92400e; font-weight: bold; background-color: #fef3c7; padding: 2px 8px; border-radius: 4px;">⚠️ Missing</span>'
    return val

def render_executive_summary(summary_text: str):
    """Render the executive summary as formatted bullet points."""
    lines = [l.strip() for l in summary_text.split('\n') if l.strip()]
    bullets = []
    for line in lines:
        # Normalise various bullet styles to •
        if line.startswith(('•', '-', '*', '–')):
            bullets.append(line.lstrip('•-*– ').strip())
        else:
            bullets.append(line)

    summary_html = "".join(
        f'<div style="display:flex; align-items:flex-start; gap:10px; margin-bottom:10px;">'
        f'<span style="color:#1d4ed8; font-size:18px; line-height:1.4;">•</span>'
        f'<span style="font-size:14px; line-height:1.6; color:#1e293b;">{b}</span>'
        f'</div>'
        for b in bullets
    )
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#eff6ff,#f0fdf4); border-left:4px solid #1d4ed8; '
        f'border-radius:8px; padding:20px 24px; margin-bottom:8px;">'
        f'{summary_html}</div>',
        unsafe_allow_html=True
    )

def render_main_interface():
    # ── Model Selector ────────────────────────────────────────────────────────
    st.markdown("#### Analysis Configuration")
    col1, col2 = st.columns([2, 3])
    with col1:
        selected_model_label = st.selectbox(
            "AI Model",
            options=list(AVAILABLE_MODELS.keys()),
            index=0,
            help="Flash is faster and cost-efficient. Pro is more thorough and recommended for critical audits.",
            key="model_selector"
        )
    selected_model = AVAILABLE_MODELS[selected_model_label]
    with col2:
        st.markdown("")
        st.markdown("")
        if "Pro" in selected_model_label:
            st.info("🧠 **Pro mode:** Deep reasoning, exhaustive analysis. Takes ~60–90 seconds.")
        else:
            st.info("⚡ **Flash mode:** Fast and efficient. Recommended for initial assessments.")

    st.markdown("---")

    # ── Document Upload ───────────────────────────────────────────────────────
    st.markdown("#### Document Acquisition")
    st.markdown("Securely upload internal policies (PDF, DOCX, PPTX) for comprehensive assessment against current DPDP regulatory standards.")

    uploaded_files = st.file_uploader(
        "Select Policy Documents",
        type=["pdf", "docx", "pptx"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_files:
        if st.button("Initiate Compliance Assessment", type="primary"):
            with st.spinner(f"Running exhaustive DPDP audit via {selected_model_label}... This may take up to 90 seconds."):
                text_content, file_names = process_uploaded_files(uploaded_files)
                st.session_state['policy_text'] = text_content
                st.session_state['file_names'] = file_names
                st.session_state['selected_model'] = selected_model

                # Run analysis
                report_df, executive_summary = analyze_dpdp_compliance(text_content, selected_model)
                if report_df is not None:
                    if "Error" in report_df.columns:
                        st.error(report_df.iloc[0]["Error"])
                    elif report_df.empty:
                        st.warning("The framework executed, but returned an empty assessment. Please verify the document format and content.")
                    else:
                        st.session_state['compliance_report'] = report_df
                        if executive_summary:
                            st.session_state['executive_summary'] = executive_summary
                        st.success(f"✅ Assessment completed across {len(file_names)} document(s) — {len(report_df)} findings produced.")
                else:
                    st.error("Failed to execute compliance framework: An unexpected system error occurred.")

    # ── Assessment Overview (Executive Summary) ───────────────────────────────
    if 'executive_summary' in st.session_state:
        st.markdown("---")
        st.markdown("#### 📋 Executive Assessment Overview")
        render_executive_summary(st.session_state['executive_summary'])

    # ── Gap Analysis Report Table ─────────────────────────────────────────────
    if 'compliance_report' in st.session_state:
        df = st.session_state['compliance_report']
        st.markdown("---")
        st.markdown("#### 📊 DPDP Gap Analysis Report")

        # Check if it's a plain message row vs a full report
        if df.columns[0] == "Message" and len(df.columns) == 1:
            st.info(df.iloc[0]["Message"])
        else:
            # Status counts
            if "Compliant or Non-Compliant" in df.columns:
                counts = df["Compliant or Non-Compliant"].value_counts()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Findings", len(df))
                m2.metric("✅ Compliant", counts.get("Compliant", 0))
                m3.metric("❌ Non-Compliant", counts.get("Non-Compliant", 0))
                m4.metric("⚠️ Missing", counts.get("Missing", 0))

            # Filter mechanism
            status_filter = st.radio(
                "Filter by Status",
                ["All", "Compliant", "Non-Compliant", "Missing"],
                horizontal=True,
                key="status_filter"
            )

            filtered_df = df.copy()
            if status_filter != "All":
                if "Compliant or Non-Compliant" in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df["Compliant or Non-Compliant"] == status_filter]

            if filtered_df.empty:
                st.warning(f"No {status_filter} findings found.")
            else:
                display_df = filtered_df.copy()
                if "Compliant or Non-Compliant" in display_df.columns:
                    display_df["Compliant or Non-Compliant"] = display_df["Compliant or Non-Compliant"].apply(apply_color_coding)

                html_table = display_df.to_html(index=False, classes="custom-table", escape=False)
                st.markdown(f'<div class="custom-table-wrapper">{html_table}</div>', unsafe_allow_html=True)

            # Export (unformatted original)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Export Full Report (CSV)",
                data=csv,
                file_name='dpdp_gap_analysis.csv',
                mime='text/csv',
            )

    # ── Strategic Advisory Chat ───────────────────────────────────────────────
    if 'policy_text' in st.session_state:
        st.markdown("---")
        st.markdown("#### 💬 Strategic Advisory Terminal")
        st.markdown("Query the assessment context or request specific interpretations of DPDP articles and remediation guidance.")

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("E.g., What remediation steps are needed for our consent management gap?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Synthesizing advisory response..."):
                    context = f"Uploaded IT Policy:\n{st.session_state['policy_text']}"
                    active_model = st.session_state.get('selected_model', 'gemini-2.5-flash')
                    response = chat_with_grounding(prompt, context, active_model)
                    st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
