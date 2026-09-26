# CI/CD and AI regression gate

The repository runs a GitHub Actions workflow for every pull request to `main`,
every push to `main`, and each manual run. The workflow is intentionally
offline: it does not call ATA-RAG, the Internship Coordinator, Langfuse, or an
LLM provider, and it needs no repository secrets.

## Pipeline

| Job | Checks | Failure condition |
| --- | --- | --- |
| `Ruff and pytest` | Installs Python 3.12, runs Ruff, then the complete pytest suite | A lint rule or test fails |
| `AI regression gate` | Compares checked-in baseline and candidate experiment reports | Quality decreases beyond tolerance or latency rises by more than 20% |
| `Package release candidate` | After a successful push to `main`, builds the Python wheel and source distribution and uploads them as a 14-day artifact | Either quality job fails or package building fails |

The regression gate reuses `ExperimentComparisonService`, the same comparison
logic used by the API and dashboard. Its default policy rejects:

- any pass-rate or aggregate-score decrease;
- any missing or decreased evaluator metric;
- an average-latency increase above 20%;
- a candidate that fails when its baseline passed.

The workflow's healthy candidate improves pass rate and aggregate score while
remaining inside the latency limit. The reports in
`tests/fixtures/regression/` are deterministic CI fixtures, not claims about
live application quality.

The delivery job runs only after a successful push to `main`. It produces a
tested release-candidate artifact rather than deploying the local MVP and its
external application dependencies to a public environment.

## Run the checks locally on Windows

From the repository root in PowerShell, with the virtual environment active:

```powershell
python -m pip install -e ".[ui,dev]"
python -m ruff check .
python -m pytest -q
python scripts/check_regression.py `
    --baseline tests/fixtures/regression/baseline.json `
    --candidate tests/fixtures/regression/candidate.json
git diff --check
```

The healthy command must print `RESULT: PASS` and exit with code `0`.

## Demonstrate that a regression is blocked

The repository includes a deliberately worse candidate. Run it locally:

```powershell
python scripts/check_regression.py `
    --baseline tests/fixtures/regression/baseline.json `
    --candidate tests/fixtures/regression/regressed_candidate.json
$LASTEXITCODE
```

Expected result: the command explains the score, metric, and latency
regressions, prints `RESULT: FAIL`, and `$LASTEXITCODE` is `1`. This failure is
intentional and proves that the gate blocks a regressed candidate.

To demonstrate the same behavior in GitHub:

1. Open the repository's **Actions** tab and select **CI**.
2. Choose **Run workflow**.
3. Enable **Run the deliberately regressed candidate**.
4. Run the workflow and open **AI regression gate** to see its reasons.
5. Run the workflow again with the option disabled so the latest run is green.

The regression command also writes a metric table and failure reasons to the
GitHub Actions job summary.

After the pull request is merged, open the successful workflow run and find
the generated wheel and source distribution under **Artifacts**. Downloading
that artifact provides evidence that the continuous-delivery job completed.

## Using real experiment reports later

The CLI accepts any two compatible serialized `ExperimentReport` JSON files:

```powershell
python scripts/check_regression.py `
    --baseline path/to/baseline.json `
    --candidate path/to/candidate.json `
    --score-tolerance 0.01 `
    --max-latency-increase-percent 20
```

Both reports must use the same system, dataset ID, and dataset version. Live
evaluation remains a separate release-validation step because it depends on
external services, credentials, model availability, and larger execution
times.
