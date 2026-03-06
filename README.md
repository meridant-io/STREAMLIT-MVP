# E2CAF Streamlit MVP

Streamlit web UI for your E2CAF FastAPI service.

## Run locally
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env (set E2CAF_DB_PATH, ANTHROPIC_API_KEY, etc.)
streamlit run app.py
```
