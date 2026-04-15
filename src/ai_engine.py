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

def analyze_dpdp_compliance(policy_text: str, model_name: str = "gemini-2.5-flash") -> tuple[pd.DataFrame, str | None]:
    """
    Evaluates the given IT policy against the DPDP Act using a two-step approach:
    Step 1: Google Search grounding to fetch accurate, up-to-date DPDP regulatory context.
    Step 2: Exhaustive structured JSON analysis using the grounded context + document.
    """
    import time
    import re

    def call_model(contents, config, max_retries=4, delay_base=15):
        """Helper: call the selected Gemini model with retries on 429/503."""
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
                    print(f"Rate limit hit, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait)
                    continue
                raise
        return None

    # ── STEP 1: Google Search Grounding — fetch verified DPDP regulatory context ─
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
        "Section 33 (Penalties — up to ₹250 crore), Section 36 (Data Protection Board). "
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
            "Sec 8: Data Fiduciary obligations — accuracy, security safeguards, breach notification within 72 hours, erasure when purpose fulfilled.\n"
            "Sec 9: Verifiable parental consent for minors; no behavioural tracking of children.\n"
            "Sec 10: Significant Data Fiduciaries — DPIA, data audits, DPO appointment.\n"
            "Sec 11: Right to access — summary of data processed, processing activities, list of other fiduciaries.\n"
            "Sec 12: Right to correction, completion, updating, erasure of personal data.\n"
            "Sec 13: Grievance redressal mechanism mandatory.\n"
            "Sec 14: Right to nominate another person to exercise rights in case of death/incapacity.\n"
            "Sec 16: Government exemptions for national security, law enforcement.\n"
            "Sec 33: Penalties — up to ₹250 crore per breach instance.\n"
            "Sec 36: Data Protection Board adjudicates complaints."
        )

    # ── STEP 2: Exhaustive JSON Compliance Analysis ───────────────────────────
    analysis_prompt = f"""
You are a Partner-level IT Compliance & Risk Advisor at a Big-4 consulting firm (McKinsey/Deloitte/PwC standard).
You are conducting a formal DPDP Act compliance audit of a client's policy document.
Your report will be presented directly to the client's Board of Directors and CISO.

=== VERIFIED DPDP REGULATORY CONTEXT (Google Search Grounded) ===
{grounded_context[:10000]}

=== YOUR MANDATE ===
Perform an EXHAUSTIVE, section-by-section compliance gap analysis. You MUST:
1. Evaluate the policy against EVERY DPDP section listed in the regulatory context above.
2. Identify ALL clauses in the document that are Compliant with DPDP.
3. Identify ALL clauses in the document that are Non-Compliant with DPDP (present but inadequate).
4. Identify ALL DPDP requirements that are COMPLETELY MISSING from the document.
5. Produce AT LEAST 15-20 findings. A report with fewer than 10 findings is UNACCEPTABLE for a top-tier audit.
6. The executive_summary must be 5-7 crisp bullet points using • symbols, highlight critical risk areas, overall compliance posture, and top 3 recommended actions.

Each finding must reference the exact DPDP section number.

Return ONLY valid JSON — no preamble, no markdown fences, no explanation outside the JSON.

{{
  "executive_summary": "• Bullet 1 (Overall posture)\\n• Bullet 2 (Critical gap 1)\\n• Bullet 3 (Critical gap 2)\\n• Bullet 4 (Compliant area)\\n• Bullet 5 (Top recommendation)",
  "gap_analysis": [
    {{
      "Key Pointer of the Policy Given": "Exact description of the policy clause or, for 'Missing' items, the DPDP requirement that is absent",
      "Compliant or Non-Compliant": "Compliant",
      "Missing Pointers": "N/A (if Compliant) OR specific remediation action required",
      "DPDP Article/Guideline Number": "Section X, DPDP Act 2023 — [brief section title]"
    }}
  ]
}}

If the document has ZERO applicability to personal data or data protection (e.g., a purely financial/HR/procurement policy), return:
{{
  "executive_summary": "The uploaded policy type does not hold implications under the DPDP Act.",
  "gap_analysis": []
}}

=== CLIENT POLICY DOCUMENT ===
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
        return pd.DataFrame([{"Error": f"AI analysis error: {error_msg}"}]), None

    if raw_text is None:
        return pd.DataFrame([{"Error": "AI service returned no content. Please try again."}]), None

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
        print(f"Analysis complete: {len(gap_data)} findings produced.")
    else:
        gap_data = [{"Message": f"Could not parse response. Raw: {raw_text[:500]}"}]
        exec_summary = None

    if not gap_data:
        if exec_summary and "does not hold implications" in exec_summary:
            gap_data = [{"Message": exec_summary}]
        else:
            gap_data = [{"Message": "No compliance gaps identified. Please verify the document content is relevant to personal data processing."}]

    return pd.DataFrame(gap_data), exec_summary


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
