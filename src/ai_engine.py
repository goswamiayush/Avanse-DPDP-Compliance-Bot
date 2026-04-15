import os
import json
import pandas as pd
from google import genai
from google.genai import types

# Initialize the Gemini Client
try:
    import streamlit as st
    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
except:
    api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

# Available models for the UI selector
AVAILABLE_MODELS = {
    "⚡ Gemini 2.5 Flash (Faster)": "gemini-2.5-flash",
    "🧠 Gemini 2.5 Pro (More Thorough)": "gemini-2.5-pro",
}


def analyze_dpdp_compliance(policy_text: str, model_name: str = "gemini-2.5-flash"):
    """
    Two-step DPDP compliance analysis:
      Step 1 — Google Search grounding for verified DPDP regulatory context.
      Step 2 — Two-phase JSON analysis:
                Phase A: Identify document type & gate DPDP applicability.
                Phase B: Exhaustive gap analysis (only if applicable).

    Returns: (DataFrame, executive_summary, document_type, dpdp_applicable)
    """
    import time
    import re

    def call_model(contents, config, max_retries=4, delay_base=15):
        """Call the selected Gemini model with retry on 429/503."""
        for attempt in range(max_retries):
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
            except Exception as e:
                err = str(e)
                if ('429' in err or '503' in err) and attempt < max_retries - 1:
                    wait = delay_base * (attempt + 1)
                    print(f"Rate limit — retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue
                raise
        return None

    # ── STEP 1: Google Search Grounding — verified DPDP regulatory context ────
    grounding_prompt = (
        "Provide a comprehensive and exhaustive summary of ALL compliance obligations under the "
        "Digital Personal Data Protection (DPDP) Act, 2023 (India). "
        "List EVERY section from Section 4 to Section 40, including: "
        "Section 4 (Grounds for processing), Section 5 (Notice), Section 6 (Consent), "
        "Section 7 (Certain legitimate uses), Section 8 (Obligations of Data Fiduciary), "
        "Section 9 (Processing of personal data of children), Section 10 (Significant Data Fiduciary), "
        "Section 11 (Right to access information), Section 12 (Right to correction and erasure), "
        "Section 13 (Right of grievance redressal), Section 14 (Right to nominate), "
        "Section 16 (Exemptions), Section 17 (Additional exemptions), "
        "Section 33 (Penalties — up to Rs.250 crore), Section 36 (Data Protection Board). "
        "For each section, state: the exact obligation, who it applies to, and what non-compliance looks like. "
        "Be precise, exhaustive, and cite section numbers exactly."
    )

    grounded_context = ""
    try:
        grounding_response = call_model(
            contents=grounding_prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.1
            )
        )
        if grounding_response and grounding_response.text:
            grounded_context = grounding_response.text.strip()
            print(f"Grounding step succeeded: {len(grounded_context)} chars")
    except Exception as e:
        print(f"Grounding step failed (using fallback): {e}")
        grounded_context = (
            "DPDP Act, 2023 (India) — Key Obligations:\n"
            "Sec 4: Lawful grounds for processing personal data.\n"
            "Sec 5: Data Fiduciary must give clear, itemized notice before/during consent.\n"
            "Sec 6: Consent must be free, specific, informed, unconditional, and unambiguous.\n"
            "Sec 7: Legitimate uses (state functions, medical emergencies, employment).\n"
            "Sec 8: Data Fiduciary obligations — accuracy, security safeguards, breach notification, erasure when purpose fulfilled.\n"
            "Sec 9: Verifiable parental consent for minors; no behavioural tracking of children.\n"
            "Sec 10: Significant Data Fiduciaries — DPIA, data audits, DPO appointment.\n"
            "Sec 11: Right to access — summary of data processed, processing activities.\n"
            "Sec 12: Right to correction, completion, updating, erasure of personal data.\n"
            "Sec 13: Grievance redressal mechanism mandatory.\n"
            "Sec 14: Right to nominate another person to exercise rights in case of death/incapacity.\n"
            "Sec 33: Penalties — up to Rs.250 crore per breach instance.\n"
            "Sec 36: Data Protection Board adjudicates complaints."
        )

    # ── STEP 2: Two-Phase JSON Analysis ──────────────────────────────────────
    analysis_prompt = f"""
You are a Partner-level IT Compliance & Risk Advisor at a Big-4 consulting firm.
Your report will be presented directly to the client's Board of Directors and CISO.

=== VERIFIED DPDP REGULATORY CONTEXT (Google Search Grounded) ===
{grounded_context[:10000]}

=== PHASE A — DOCUMENT IDENTIFICATION (MANDATORY FIRST STEP) ===
Carefully read the uploaded document below and determine:

1. What type of document is this? Be specific.
   Examples: "IT Security Policy", "Data Privacy Policy", "Employee Handbook",
   "Invoice / Financial Document", "Academic Research Paper", "News Article",
   "Product Brochure", "Legal Contract", "Random PDF", "Technical Manual", etc.

2. Is this a formal organisational policy, procedure, standard, or governance document?
   Answer: true or false

3. Does this document directly involve the collection, storage, processing, transfer,
   or sharing of PERSONAL DATA of identifiable individuals?
   Answer: true or false

4. DPDP Applicability Decision:
   Set dpdp_applicable = true ONLY IF:
     - The document IS a formal policy/procedure/governance document, AND
     - It directly involves personal data of identifiable individuals.
   Set dpdp_applicable = false for:
     - Invoices, receipts, financial statements
     - Research papers, academic articles, news
     - Product brochures, marketing material
     - Random or unrelated PDFs
     - Any non-policy document

=== PHASE B — COMPLIANCE ANALYSIS ===

IF dpdp_applicable is TRUE:
  Perform an EXHAUSTIVE section-by-section gap analysis. You MUST:
  - Evaluate the policy against EVERY DPDP section in the regulatory context.
  - Identify ALL Compliant, Non-Compliant, and Missing items.
  - Produce AT LEAST 15-25 detailed findings.
  - Executive summary: 5-7 bullet points — document identified, overall posture, top 3 critical gaps, top recommendation.

IF dpdp_applicable is FALSE:
  - Set gap_analysis to an empty array: []
  - DO NOT fabricate or invent any compliance findings.
  - Executive summary must clearly state:
    * What the document actually IS (be specific about content)
    * Why DPDP does NOT apply to it
    * That no compliance assessment has been conducted

Return ONLY valid JSON. No preamble, no markdown fences, no explanation outside the JSON.

{{
  "document_type": "Specific type of the uploaded document",
  "dpdp_applicable": true,
  "executive_summary": "• Document identified: [type]\\n• [Posture / Not applicable reason]\\n• [Finding or explanation]\\n• [Recommendation if applicable]",
  "gap_analysis": [
    {{
      "Key Pointer of the Policy Given": "Exact policy clause or absent DPDP requirement",
      "Compliant or Non-Compliant": "Compliant",
      "Missing Pointers": "N/A or specific remediation action",
      "DPDP Article/Guideline Number": "Section X, DPDP Act 2023 — [section title]"
    }}
  ]
}}

=== UPLOADED DOCUMENT ===
{policy_text[:28000]}
"""

    raw_text = None
    try:
        analysis_response = call_model(
            contents=analysis_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        if analysis_response and analysis_response.text:
            raw_text = analysis_response.text.strip()
    except Exception as e:
        error_msg = str(e)
        print(f"Analysis step error: {error_msg}")
        return pd.DataFrame([{"Error": f"AI analysis error: {error_msg}"}]), None, "Unknown", False

    if raw_text is None:
        return pd.DataFrame([{"Error": "AI service returned no content. Please retry."}]), None, "Unknown", False

    # ── Parse JSON (with fallback fence-stripping) ────────────────────────────
    data = None
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        clean = re.sub(r'^```(?:json)?\s*\n?', '', raw_text).strip()
        clean = re.sub(r'\n?```\s*$', '', clean).strip()
        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

    if data is not None:
        exec_summary = data.get("executive_summary", "No summary provided.")
        gap_data = data.get("gap_analysis", [])
        document_type = data.get("document_type", "Unknown document type")
        dpdp_applicable = data.get("dpdp_applicable", True)
        print(f"Document: '{document_type}' | Applicable: {dpdp_applicable} | Findings: {len(gap_data)}")
    else:
        exec_summary = None
        gap_data = [{"Message": f"Could not parse AI response. Raw output: {raw_text[:500]}"}]
        document_type = "Unknown"
        dpdp_applicable = False

    if dpdp_applicable and not gap_data:
        gap_data = [{"Message": "No specific compliance gaps identified. Please verify the document contains sufficient policy detail."}]

    result_df = pd.DataFrame(gap_data) if gap_data else pd.DataFrame()
    return result_df, exec_summary, document_type, dpdp_applicable


def chat_with_grounding(user_message: str, document_context: str, model_name: str = "gemini-2.5-flash") -> str:
    """
    Answers questions using the uploaded documents and Google Search Grounding with a DPDP expert persona.
    """
    system_instruction = f"""
    You are a Senior Advisory Consultant and DPDP Regulatory Expert at a top-tier consulting firm.
    Your role is to address the client's queries regarding the uploaded IT policy and its compliance with the DPDP Act, 2023.

    Rules:
    1. Utilize Google Search Grounding to cite the latest and most accurate DPDP rules.
    2. Quote precise DPDP Act sections, sub-sections, and article numbers where applicable.
    3. Maintain a formal, authoritative, and concise tone appropriate for top-tier enterprise consulting.
    4. Provide actionable, specific guidance — not generic advice.
    5. If the query relates to a gap in the policy, suggest exact remediation language.

    --- Client IT Policy Context ---
    {document_context[:50000]}
    """

    import time
    max_retries = 6
    retry_delay_base = 10
    output = None
    response = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[system_instruction, user_message],
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.2
                )
            )
            output = response.text
            break
        except Exception as e:
            error_msg = str(e)
            if ('503' in error_msg or '429' in error_msg) and attempt < max_retries - 1:
                time.sleep(retry_delay_base * (attempt + 1))
                continue
            return f"System encountered an error during advisory synthesis: {error_msg}"

    if output is None:
        return "All retries exhausted. The AI service is temporarily unavailable."

    if response and hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
            metadata = candidate.grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                output += "\n\n**Citations:**\n"
                for idx, chunk in enumerate(metadata.grounding_chunks):
                    if hasattr(chunk, 'web') and chunk.web:
                        output += f"[{idx+1}] [{chunk.web.title}]({chunk.web.uri})\n"

    return output
