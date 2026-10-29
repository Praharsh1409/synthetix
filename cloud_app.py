"""Community Cloud entry point. Keep app.py's local behaviour unchanged."""
from pathlib import Path
import runpy
import secrets
import streamlit as st
from runtime_paths import visitor_workspace

if 'cloud_workspace_id' not in st.session_state:
    st.session_state['cloud_workspace_id'] = secrets.token_hex(32)

with visitor_workspace(st.session_state['cloud_workspace_id']):
    runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
