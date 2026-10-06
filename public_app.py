"""Public read-only entrypoint for Streamlit Community Cloud."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__',
               init_globals={'DASHBOARD_PUBLIC_MODE': True})
