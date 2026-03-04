# E2CAF Streamlit MVP

Streamlit web UI for your E2CAF FastAPI service.

## Run locally
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env (API_BASE_URL)
streamlit run app.py
```
