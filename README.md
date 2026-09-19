# Dashboard

From the project root on Windows, install the optional dashboard dependency:

```powershell
python -m pip install -e ".[ui,dev]"
```

Keep the API running in one terminal:

```powershell
python -m uvicorn app.main:app --reload --port 8100
```

In a second terminal, open the Streamlit dashboard on port 8501:

```powershell
python -m streamlit run dashboard/app.py --server.port 8501
```

Open http://127.0.0.1:8501. The sidebar's API URL defaults to
`http://127.0.0.1:8100`. The dashboard can browse datasets, launch experiments,
inspect saved case results, and compare two runs of the same dataset. Running
an experiment invokes the configured application adapter and saves a new report.

The ATA-RAG preset includes `semantic_facts`; it requires the
`EVALUATOR_LLM_*` settings in the backend `.env`. Edit the JSON evaluator list
in the UI if you want to run only deterministic checks.
