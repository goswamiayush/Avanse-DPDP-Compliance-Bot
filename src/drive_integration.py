import streamlit as st
import os
import io
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from src.document_processor import extract_text_from_pdf

# Need the secrets toml to have Google Cloud OAuth credentials configured.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CLIENT_SECRETS_FILE = ".streamlit/client_secret.json" # Users need to provide this.

def get_auth_flow():
    # Try st.secrets first (Streamlit Cloud deployment)
    if "gcp_oauth" in st.secrets:
        client_config = {
            "web": {
                "client_id": st.secrets["gcp_oauth"]["client_id"],
                "project_id": st.secrets["gcp_oauth"]["project_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": st.secrets["gcp_oauth"]["client_secret"],
                "redirect_uris": [st.secrets["gcp_oauth"]["redirect_uri"]]
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=st.secrets["gcp_oauth"]["redirect_uri"]
        )
        return flow
        
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return None
        
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:8501' # Streamlit default port locally
    )
    return flow

def render_google_drive_auth_and_fetch():
    """Renders the Google SSO button and Drive fetch logic."""
    flow = get_auth_flow()
    
    if flow is not None:
        if not st.session_state.google_credentials:
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            st.markdown(f'<a href="{auth_url}" target="_self" class="stButton"><button style="background-color: #4285F4; color: white; padding: 10px; border-radius: 5px; border: None;">Sign in with Google</button></a>', unsafe_allow_html=True)
            
            # Very basic callback handling for Streamlit
            if 'code' in st.query_params:
                try:
                    flow.fetch_token(code=st.query_params['code'])
                    st.session_state.google_credentials = flow.credentials
                    st.success("Authentication Successful! Please clear URL params and reload if stuck.")
                except Exception as e:
                    st.error(f"Authentication failed: {e}")
        
        if st.session_state.google_credentials:
            st.success("Authenticated with Google SSO.")
            folder_url = st.text_input("Enter Google Drive Folder URL", "https://drive.google.com/drive/folders/1xO7Ld901ioOvZusabuhYR9xJ0lEfqYxH")
            
            if st.button("Fetch Files from Folder"):
                try:
                    folder_id = folder_url.split('/')[-1].split('?')[0] # Basic parsing
                    service = build('drive', 'v3', credentials=st.session_state.google_credentials)
                    query = f"'{folder_id}' in parents and trashed=False"
                    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
                    items = results.get('files', [])
                    
                    if not items:
                        st.warning("No files found in this folder or folder is not accessible.")
                        return "", []
                        
                    fetched_names = []
                    combined_text = ""
                    
                    progress = st.progress(0, text="Downloading files...")
                    for idx, item in enumerate(items):
                        if 'pdf' in item['mimeType'] or 'document' in item['mimeType']:
                            request = service.files().get_media(fileId=item['id'])
                            fh = io.BytesIO()
                            downloader = MediaIoBaseDownload(fh, request)
                            done = False
                            while done is False:
                                status, done = downloader.next_chunk()
                            
                            fh.seek(0)
                            if 'pdf' in item['mimeType']:
                                text = extract_text_from_pdf(fh)
                                combined_text += f"\n\n--- Start of Drive File: {item['name']} ---\n{text}\n"
                                fetched_names.append(item['name'])
                                
                        progress.progress((idx + 1) / len(items), text=f"Downloaded {item['name']}")
                    progress.empty()
                    return combined_text, fetched_names
                    
                except Exception as e:
                    st.error(f"Failed to fetch from Drive: {e}")
                    return "", []
            
    else:
        st.warning("Google OAuth Credentials not configured. Please add `gcp_oauth` to Streamlit Secrets or provide `client_secret.json` locally.")
        
    return "", []
