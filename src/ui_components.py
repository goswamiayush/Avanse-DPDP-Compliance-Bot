import streamlit as st
import pandas as pd
from src.document_processor import process_uploaded_files
from src.ai_engine import analyze_dpdp_compliance, chat_with_grounding, generate_executive_summary

def apply_color_coding(val):
    if val == 'Compliant':
        return '<span style="color: #15803d; font-weight: bold; background-color: #dcfce7; padding: 2px 6px; border-radius: 4px;">Compliant</span>'
    elif val == 'Non-Compliant':
        return '<span style="color: #b91c1c; font-weight: bold; background-color: #fee2e2; padding: 2px 6px; border-radius: 4px;">Non-Compliant</span>'
    elif val == 'Missing':
        return '<span style="color: #4b5563; font-weight: bold; background-color: #f3f4f6; padding: 2px 6px; border-radius: 4px;">Missing</span>'
    return val

def render_main_interface():
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
            with st.spinner("Executing document processing and compliance mapping..."):
                text_content, file_names = process_uploaded_files(uploaded_files)
                st.session_state['policy_text'] = text_content
                st.session_state['file_names'] = file_names
                
                # Run analysis
                report_df = analyze_dpdp_compliance(text_content)
                if report_df is not None:
                    if "Error" in report_df.columns:
                        st.error(report_df.iloc[0]["Error"])
                    elif report_df.empty:
                        st.warning("The framework executed, but returned an empty assessment. Please verify the document format and content.")
                    else:
                        st.session_state['compliance_report'] = report_df
                        
                        # Run Summary if this is a valid tabular report
                        if 'Message' not in report_df.columns or len(report_df.columns) > 1:
                            st.info("Applying a 2-minute API cooldown to respect Free Tier limits... please wait.")
                            import time
                            time.sleep(120)
                            with st.spinner("Synthesizing Executive Briefing..."):
                                summary = generate_executive_summary(text_content, report_df)
                                st.session_state['executive_summary'] = summary
                                
                        st.success(f"Assessment completed across {len(file_names)} document(s).")
                else:
                    st.error("Failed to execute compliance framework: An unexpected system error occurred.")

    # Assessment Overview
    if 'executive_summary' in st.session_state:
        st.markdown("---")
        st.markdown("#### Assessment Overview")
        st.info(st.session_state['executive_summary'])

    # Show Report
    if 'compliance_report' in st.session_state:
        df = st.session_state['compliance_report']
        st.markdown("---")
        st.markdown("#### DPDP Gap Analysis Report")
        
        # Determine if it's the applicability abort message instead of a full table
        if df.columns[0] == "Message" and len(df.columns) == 1:
            st.info(df.iloc[0]["Message"])
        else:
            # Filter mechanism
            status_filter = st.radio("Filter Rules by Status", ["All", "Compliant", "Non-Compliant", "Missing"], horizontal=True)
            
            filtered_df = df.copy()
            if status_filter != "All":
                # Ensure the column exists before filtering
                if "Compliant or Non-Compliant" in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df["Compliant or Non-Compliant"] == status_filter]
            
            if filtered_df.empty:
                st.warning(f"No {status_filter} rules found.")
            else:
                # Apply Color Coding
                if "Compliant or Non-Compliant" in filtered_df.columns:
                    filtered_df["Compliant or Non-Compliant"] = filtered_df["Compliant or Non-Compliant"].apply(apply_color_coding)
                
                # Convert DataFrame to corporate styled HTML table
                html_table = filtered_df.to_html(index=False, classes="custom-table", escape=False)
                st.markdown(f'<div class="custom-table-wrapper">{html_table}</div>', unsafe_allow_html=True)
            
            # Allow downloading of the unfiltered standard report (no HTML spans)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Full Report (CSV)",
                data=csv,
                file_name='dpdp_gap_analysis.csv',
                mime='text/csv',
            )

    # Show Chat Interface
    if 'policy_text' in st.session_state:
        st.markdown("---")
        st.markdown("#### Strategic Advisory Terminal")
        st.markdown("Query the assessment context or request specific interpretations of DPDP articles.")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("E.g., Which article of the DPDP act covers data fiduciary obligations mentioned in our policy?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Synthesizing advisory response..."):
                    context = f"Uploaded IT Policy:\n{st.session_state['policy_text']}"
                    response = chat_with_grounding(prompt, context)
                    st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
