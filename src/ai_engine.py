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
    Evaluates the given IT policy against the latest DPDP guidelines using Gemini and Google Search Grounding.
    Returns a tuple containing a DataFrame with the compliance results and a string for the executive summary.
    """
    prompt = f"""
    You are a Senior IT Compliance & Risk Advisor at a top-tier consulting firm. 
    Your task is to conduct a formal assessment of the provided "client policy document" against the *latest* Digital Personal Data Protection (DPDP) Act.
    
    STEP 1: Applicability Check
    Determine the type of policy uploaded. Does the DPDP Act even apply to this?
    
    STEP 2: Compliance Gap Analysis & Executive Summary
    If DPDP applies, utilize Google Search Grounding to reference the most accurate, up-to-date DPDP rules, acts, and article numbers.
    Analyze the policy and extract both standard pointers AND rules that are completely MISSING from the document but required by DPDP.
    Finally, formulate a crisp, authoritative executive summary based on your findings (3-4 bullet points highlighting key compliance gaps or successes).
    
    Output ONLY a valid JSON object, with no markdown formatting outside of the string values.
    
    Format of the JSON object:
    {{
      "executive_summary": "Crisp markdown bullet points summarizing the most critical takeaways regarding Compliant, Non-Compliant, and Missing sections. State the assumed name or core topic of the policy.",
      "gap_analysis": [
        {{
          "Key Pointer of the Policy Given": "Brief summary... MUST include [Page X]",
          "Compliant or Non-Compliant": "'Compliant', 'Non-Compliant', or 'Missing'",
          "Missing Pointers": "Remediation steps...",
          "DPDP Article/Guideline Number": "Exact clause..."
        }}
      ]
    }}

    If the document has ZERO applicability to DPDP, you must still return the JSON object, but leave the gap_analysis array empty:
    {{
      "executive_summary": "The uploaded policy type does not hold implications under the DPDP Act.",
      "gap_analysis": []
    }}

    --- Client Policy Document Context (including location markers) ---
    {policy_text[:30000]}
    """

    import time
    import re
    max_retries = 6
    retry_delay_base = 10
    raw_text = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.1
                )
            )
            raw_text = response.text.strip()
            break
        except Exception as e:
            error_msg = str(e)
            if ('503' in error_msg or '429' in error_msg) and attempt < max_retries - 1:
                time.sleep(retry_delay_base * (attempt + 1))
                continue
            print(f"Error generating compliance check: {error_msg}")
            return pd.DataFrame([{"Error": f"System encountered an error during parsing: {error_msg}"}]), None

    # If all retries exhausted without a response
    if raw_text is None:
        return pd.DataFrame([{"Error": "All retries exhausted. The AI service is temporarily unavailable."}]), None

    # DEBUG: Log raw model response to Streamlit Cloud logs
    print("=== RAW AI RESPONSE (first 2000 chars) ===")
    print(raw_text[:2000])
    print("=== END RAW RESPONSE ===")

    # Step 1: Strip markdown code fences if the model wrapped the JSON (e.g. ```json ... ```)
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r'^```(?:json)?\s*\n?', '', clean_text)
        clean_text = re.sub(r'\n?```\s*$', '', clean_text)
        clean_text = clean_text.strip()

    # Step 2: Try a direct JSON parse on the cleaned text first
    data = None
    try:
        data = json.loads(clean_text)
    except json.JSONDecodeError as je:
        print(f"Direct JSON parse failed: {je}")
        # Step 3: Fall back to regex extraction of the first {...} block
        match = re.search(r"\{.*\}", clean_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError as je2:
                print(f"Regex JSON parse also failed: {je2}")

    if data is not None:
        exec_summary = data.get("executive_summary", "No summary provided.")
        gap_data = data.get("gap_analysis", [])
        print(f"DEBUG: gap_analysis has {len(gap_data)} items. Keys in data: {list(data.keys())}")
    else:
        print("DEBUG: Could not parse any JSON from the response.")
        gap_data = [{"Message": raw_text}]
        exec_summary = None

    if not gap_data:
        print(f"DEBUG: gap_data is empty. exec_summary={exec_summary[:100] if exec_summary else None}")
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

