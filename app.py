import streamlit as st
import os
from src.ui_components import render_main_interface

st.set_page_config(page_title="DPDP Compliance Assessment", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Base font and background */
    .stApp {
        background-color: #FAFAFA;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    /* Headers */
    .main-header {
        color: #0A192F;
        font-weight: 600;
        margin-bottom: 5px;
        font-size: 2.2rem;
        letter-spacing: -0.01em;
    }
    .sub-header {
        color: #4A5568;
        font-weight: 400;
        margin-top: 0px;
        margin-bottom: 40px;
        font-size: 1.1rem;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 20px;
    }
    /* Buttons */
    .stButton > button {
        background-color: #0B3A5E !important;
        color: white !important;
        border-radius: 4px;
        font-weight: 500;
        border: none;
        padding: 0.5rem 1rem;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #125182 !important;
    }
    
    /* Custom Responsive Table styling for the gap analysis */
    .custom-table-wrapper {
        width: 100%;
        overflow-x: auto;
        margin-bottom: 20px;
        border-radius: 6px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        background-color: white;
    }
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 0.95rem;
    }
    .custom-table thead tr {
        background-color: #0A192F;
        color: #ffffff;
        text-align: left;
    }
    .custom-table th, .custom-table td {
        padding: 12px 15px;
        border-bottom: 1px solid #E2E8F0;
        vertical-align: top;
    }
    .custom-table tbody tr {
        background-color: #ffffff;
    }
    /* Braided / Striped rows */
    .custom-table tbody tr:nth-of-type(even) {
        background-color: #F8FAFC;
    }
    .custom-table tbody tr:hover {
        background-color: #E2E8F0; 
    }
    
    /* Mobile compatibility */
    @media (max-width: 768px) {
        .custom-table {
            font-size: 0.85rem;
        }
        .main-header {
            font-size: 1.6rem;
        }
        .sub-header {
            font-size: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>Data Protection & Privacy Compliance Framework</h1>", unsafe_allow_html=True)
st.markdown("<h3 class='sub-header'>Automated evaluation of internal IT policies against the Digital Personal Data Protection Act (DPDP)</h3>", unsafe_allow_html=True)

render_main_interface()
