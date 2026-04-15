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

def analyze_dpdp_compliance(policy_text: str) -> tuple[pd.DataFrame, str | None]:
    """
    Evaluates the given IT policy against the DPDP Act using a two-step approach:
    Step 1: Google Search grounding to fetch accurate DPDP regulatory context.
    Step 2: Structured JSON analysis using the grounded context + document.
    """
    import time
    import re

    def call_model(contents, config, max_retries=4, delay_base=10):
        """Helper: call Gemini with retries on 429/503."""
        for attempt in range(max_retries):
            try:
                return client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=config
                )
            except Exception as e:
                err = str(e)
                if ('429' in err or '503' in err) and attempt < max_retries - 1:
                    time.sleep(delay_base * (attempt + 1))
                    continue
                raise
        return None

    # ── STEP 1: Ground the DPDP regulatory context via Google Search ──────────
    grounding_prompt = (
        "Summarize the key compliance obligations under the Digital Personal Data Protection (DPDP) Act, 2023 (India). "
        "Include all major sections (4 through 17), rights of Data Principals, obligations of Data Fiduciaries, "
        "consent requirements, data localization rules, breach notification timelines, and penalties. "
        "Be precise and cite the exact section numbers."
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
    except Exception as e:
        print(f"Grounding step failed (non-fatal): {e}")
        grounded_context = "DPDP Act, 2023 (India): Key sections include consent (Sec 6), data fiduciary obligations (Sec 8), data principal rights (Sec 11-14), breach notification (Sec 8(6)), and penalties up to ₹250 crore (Sec 33)."

    # ── STEP 2: Structured JSON compliance analysis ───────────────────────────
    analysis_prompt = f"""
You are a Senior IT Compliance & Risk Advisor. Using the verified DPDP regulatory context below, 
assess the provided client policy document and produce a structured compliance gap report.

=== VERIFIED DPDP REGULATORY CONTEXT (Google-grounded) ===
{grounded_context[:8000]}

=== TASK ===
Analyze the client policy document against the DPDP Act, 2023. For EVERY applicable DPDP section, determine:
- Is it addressed in the document? (Compliant / Non-Compliant / Missing)
- What remediation is needed if Non-Compliant or Missing?

IMPORTANT: The gap_analysis array MUST NOT be empty if the document relates to data, privacy, or personal information handling.

Return ONLY valid JSON. No preamble, no markdown, no explanation.

{{
  "executive_summary": "• Finding 1\\n• Finding 2\\n• Finding 3",
  "gap_analysis": [
    {{
      "Key Pointer of the Policy Given": "Description of the clause or missing requirement",
      "Compliant or Non-Compliant": "Compliant",
      "Missing Pointers": "N/A or remediation steps",
      "DPDP Article/Guideline Number": "Section X, DPDP Act 2023"
    }}
  ]
}}

If ZERO DPDP applicability, return:
{{
  "executive_summary": "The uploaded policy type does not hold implications under the DPDP Act.",
  "gap_analysis": []
}}

=== CLIENT POLICY DOCUMENT ===
{policy_text[:25000]}
"""

    raw_text = None
    try:
        analysis_response = call_model(
            contents=analysis_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
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

    # Parse JSON
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
    else:
        gap_data = [{"Message": f"Could not parse response. Raw: {raw_text[:500]}"}]
        exec_summary = None

    if not gap_data:
        if exec_summary and "does not hold implications" in exec_summary:
            gap_data = [{"Message": exec_summary}]
        else:
            gap_data = [{"Message": "No compliance gaps identified based on the provided policies."}]

    return pd.DataFrame(gap_data), exec_summary

def chat_with_grounding(user_message: str, document_context: str) -> str:
    """
    Answers questions using the uploaded documents and Google Search Grounding with a DPDP expert persona.
    """
    system_instruction = f"""
    You are a Senior Advisory Consultant and DPDP Regulatory Expert.
    Your role is to address the client's queries regarding the uploaded IT policy and its compliance with the DPDP framework.
    
    Rules:
    1. Utilize Google Search Grounding to cite the latest and most accurate DPDP rules.
    2. Quote precise DPDP act chapters, sub-sections, and article numbers where applicable.
    3. Maintain a formal, authoritative, and concise tone appropriate for top-tier enterprise consulting.
    4. Base your guidance on the uploaded policy context; if the context does not explicitly answer the question, leverage grounded responses to provide the statutory DPDP context.
    
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
                model='gemini-2.5-flash',
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

