# AI Evaluation Platform

Run evaluations of ATA-RAG and the Internship Coordinator, save case-level reports, and compare a candidate with a baseline. A FastAPI backend serves datasets and reports; a Streamlit dashboard lets you run and inspect experiments. Langfuse reporting is optional.

## Current datasets

| System | Adapter endpoint | Dataset ID | Cases | Dashboard preset |
| --- | --- | --- | ---: | --- |
| ATA-RAG | `POST /api/chat` on port 8001 | `ata-rag-golden-v1` | 3 | Exact match, required fields, latency, retrieval recall, semantic facts |
| Internship Coordinator | `POST /cases/intake` on port 8002 | `internship-coordinator-golden-v1` | 14 | Recommendation exact match, required fields, latency, security flag match, missing fields match |

These are development datasets (`released: false`), smaller than the project requirements. See [results and remaining work](docs/results.md).

## Local setup (Windows PowerShell)

Use Python 3.12 or 3.13. In the evaluation-platform project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[ui,dev]"
Copy-Item .env.example .env
```

Set `ATA_RAG_BASE_URL` and `INTERNSHIP_COORDINATOR_BASE_URL` in `.env` to the running applications. The defaults are `http://127.0.0.1:8001` and `http://127.0.0.1:8002`; start each application in its own project and terminal. The evaluation API does not start them.

To run the Internship dataset, retain the Coordinator project's PDF fixtures under `generated_test_dataset` and set `INTERNSHIP_COORDINATOR_ATTACHMENT_ROOT` in `.env` to that folder's absolute Windows path, such as `C:\Users\<you>\Projects\agentic-internship-coordinator\generated_test_dataset`. The adapter resolves paths such as `APP-071/APP-071_application.pdf` against that root; the Coordinator service needs access to the same filesystem.

The ATA-RAG dashboard preset uses `semantic_facts`. Set `EVALUATOR_LLM_BASE_URL`, `EVALUATOR_LLM_API_KEY`, and `EVALUATOR_LLM_MODEL` in the API's `.env` to an available provider/model. Remove the evaluator from the dashboard JSON to run deterministic checks only. Never commit `.env` or keys.

Start the API in one terminal:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
```

Start the dashboard in a second terminal:

```powershell
python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501`; the dashboard defaults to API URL `http://127.0.0.1:8100`. API docs are at `http://127.0.0.1:8100/docs`. `GET /api/v1/health` checks this API, not the two evaluated applications.

## Run and compare

1. In **Datasets**, inspect the manifest and cases. Internship PDF attachments live outside this repository.
2. In **Run experiment**, choose a dataset, review the evaluator JSON, and run it. Reports are saved in `data/experiments` by default.
3. In **History**, inspect case results and failures. Expand a case to record a human judgment, score, pass decision, reviewer, and explanation. Previous reviews appear above the form.
4. In **Compare**, select two runs of the same dataset version and adjust score and latency thresholds if needed.

The comparison API uses `GET /api/v1/experiments/compare` and query parameters `baseline_id` and `candidate_id` (optionally `score_tolerance` and `max_latency_increase_percent`). For example:

```powershell
$comparison = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8100/api/v1/experiments/compare?baseline_id=exp-e2fb1ea31d1f&candidate_id=exp-1e777045c0f5'
$comparison | Select-Object baseline_pass_rate,candidate_pass_rate,regression_detected
```

These IDs exist only when those local reports are present. After a fresh setup, use your own IDs from **History**. The comparison endpoint is `GET`, not `POST`.

Human reviews are stored separately as JSON files under `data/experiments/human_reviews` (or the configured experiment storage root). They belong to the saved experiment and case and never change its automated score. You can also use `GET` and `POST /api/v1/experiments/{experiment_id}/cases/{case_id}/reviews`; POST requires `reviewer`, `score` (0–1), `passed`, `category`, and `explanation`. Reviews are currently local records; linking them to Langfuse traces and calculating reviewer agreement are future work.

For optional Langfuse reporting, fill `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` in `.env` and restart the API. Saved runs publish experiment/case observations and scores in a background task. Verify publication in Langfuse separately; dataset synchronization has not been implemented.

## Datasets and checks

`datasets/manifest.json` lists dataset IDs, versions, paths and case counts. The internship JSONL can be rebuilt from the Coordinator project's fixtures:

```powershell
python scripts/build_internship_dataset.py --source-root "C:\Users\<you>\Projects\agentic-internship-coordinator\generated_test_dataset"
```

The builder currently selects 14 cases. If case selection changes, update the manifest count and version and review the expected labels. Released datasets require SHA-256 checksums; these entries are unreleased.

Run local checks from the project root:

```powershell
python -m ruff check .
python -m pytest -q
```

See [results and remaining work](docs/results.md) for known baselines and their limits.
