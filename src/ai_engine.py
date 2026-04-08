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

def analyze_dpdp_compliance(policy_text: str) -> pd.DataFrame:
    """
    Evaluates the given IT policy against the latest DPDP guidelines using Gemini and Google Search Grounding.
    Returns a DataFrame with the compliance results including missing rules and applicability checks.
    """
    prompt = f"""
    You are a Senior IT Compliance & Risk Advisor at a top-tier consulting firm. 
    Your task is to conduct a formal assessment of the provided "client policy document" against the *latest* Digital Personal Data Protection (DPDP) Act.
    
    STEP 1: Applicability Check
    Determine the type of policy uploaded. Does the DPDP Act even apply to this? (e.g., An Information Security Policy is impacted, but a "General Office Visitor Routing Policy" or "Standard Loan Disbursement Calculator Policy" might not hold personally identifiable data under the DPDP purview).
    If the document has ZERO applicability to DPDP, output exactly this array:
    [{{"Message": "The uploaded policy type does not hold implications under the DPDP Act."}}]
    
    STEP 2: Compliance Gap Analysis
    If DPDP applies, utilize Google Search Grounding to reference the most accurate, up-to-date DPDP rules, acts, and article numbers.
    Analyze the policy and extract both standard pointers AND rules that are completely MISSING from the document but required by DPDP.
    
    Output ONLY a valid JSON array of objects, with no markdown formatting or extra text.
    
    Format of each object in the array:
    {{
      "Key Pointer of the Policy Given": "Brief summary of the policy clause. MUST include the [Page X], [Slide Y], or [Para Z] marker exactly as seen in the text. If this is a Missing rule not in the text, write '[Not Found in Document]'",
      "Compliant or Non-Compliant": "MUST be exactly one of the three: 'Compliant', 'Non-Compliant', or 'Missing'",
      "Missing Pointers": "Specific remediation steps required to achieve compliance, or what is lacking. If Compliant, put '-'",
      "DPDP Article/Guideline Number": "The exact clause, chapter, or article number from the DPDP Act that governs this pointer"
    }}

    If the policy document is completely empty or readable, return an empty JSON array: []

    --- Client Policy Document Context (including location markers) ---
    {policy_text[:30000]}
    """

    import time
    max_retries = 3
    retry_delay_base = 5
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
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
            if '503' in error_msg and attempt < max_retries - 1:
                time.sleep(retry_delay_base * (attempt + 1))
                continue
            print(f"Error generating compliance check: {error_msg}")
            return pd.DataFrame([{"Error": f"System encountered an error during parsing: {error_msg}"}])
        
        # Robust fallback extraction to find standard array
        import re
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = [{"Message": "Warning: The AI responded with an unparseable format."}]
        else:
            # If the model didn't return an array at all, assume it's an applicability message
            data = [{"Message": raw_text}]
        
        if not data:
             return pd.DataFrame([{"Message": "No compliance gaps identified based on the provided policies."}])
             
        # If Step 1 triggers the non-applicable message directly
        if len(data) == 1 and "Message" in data[0]:
            return pd.DataFrame(data)
             
        return pd.DataFrame(data)

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
    max_retries = 3
    retry_delay_base = 5
    
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
            if '503' in error_msg and attempt < max_retries - 1:
                time.sleep(retry_delay_base * (attempt + 1))
                continue
            return f"System encountered an error during advisory synthesis: {error_msg}"
        
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                metadata = candidate.grounding_metadata
                if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                    output += "\n\n**Citations:**\n"
                    for idx, chunk in enumerate(metadata.grounding_chunks):
                        if hasattr(chunk, 'web') and chunk.web:
                            output += f"[{idx+1}] [{chunk.web.title}]({chunk.web.uri})\n"
                            
        return output

def generate_executive_summary(policy_text: str, analysis_df: pd.DataFrame) -> str:
    """
    Generates a crisp executive summary based on the parsed table and the uploaded policy document.
    """
    findings_context = analysis_df.to_string()
    
    prompt = f"""
    You are a Senior Advisory Partner communicating to a C-suite executive.
    Your objective is to provide a crisp, authoritative executive summary based on the DPDP Gap Analysis results provided.
    
    Output Format: MUST BE Markdown text only. Use bullet points. Ensure the tone is strictly professional. NO emojis.
    CRITICAL INSTRUCTION: Do NOT include any memo headers, 'To/From' blocks, subjects, dates, intro letters, or pleasantries. Start immediately with the content.
    
    Content Requirements:
    1. **Document Processed**: State the assumed name or core topic of the policy that was audited.
    2. **DPDP Applicability**: Confirm whether the DPDP act is broadly applicable to this policy type and briefly why.
    3. **Executive Highlights**: 3 to 4 crisp bullet points summarizing the most critical takeaways from the table findings regarding Compliant, Non-Compliant, and Missing sections. Quote metrics when apparent.
    
    --- Raw Findings Table ---
    {findings_context}
    
    --- Original Policy Context Head ---
    {policy_text[:3000]}
    """
    
    import time
    max_retries = 3
    retry_delay_base = 5
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2
                )
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            if '503' in error_msg and attempt < max_retries - 1:
                time.sleep(retry_delay_base * (attempt + 1))
                continue
            return f"**System Warning:** Unable to generate executive summary due to API timeout or error: {error_msg}"
