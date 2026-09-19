# Evaluation record and remaining work

The project owner observed these local runs on 17–19 September 2026. Experiment IDs refer to local reports that are not committed to this repository. Reproducing scores requires the same application versions, PDF fixtures, evaluator settings, and provider models. This small baseline is not a production accuracy estimate.

## Recorded runs

| System and run | Experiment ID | Passed cases | Pass rate | Aggregate score | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| ATA-RAG semantic baseline v3 | `exp-a9635c4ddba8` | 3/3 | 1.0 | 1.0 | `semantic_facts` and deterministic checks each scored 1.0 |
| Internship Coordinator baseline v1 | `exp-e2fb1ea31d1f` | 4/14 | 0.2857 | 0.7619 | Recommendation exact match 0.2857 |
| Internship Coordinator improved candidate v2 | `exp-1e777045c0f5` | 14/14 | 1.0 | 1.0 | Recommendation exact match 1.0 |
| Internship five-metric run, before broken-PDF label review | `exp-a19a2c1adfeb` | 12/14 | 0.8571 | 0.971 | Two broken-PDF cases had empty expected missing-field lists |
| Internship five-metric run, after label and email fix | `exp-ee904d212eab` | 14/14 | 1.0 | 1.0 | Dashboard screenshot reports dataset version 1.0.0; labels changed |

The recorded Internship comparison used `exp-e2fb1ea31d1f` as baseline and `exp-1e777045c0f5` as candidate. Pass rate rose by 0.7143, aggregate score by 0.2381, and average latency by 6.16%. With the configured 20% maximum latency increase, `regression_detected` was `false`. These are observations from the owner's environment, not checked-in test outputs or a statistical confidence estimate.

The Internship baseline mismatched 10 recommendations: two each from malicious, handwritten, missing-information, clarification, and school-requirement categories. The candidate matched all 14 expected recommendations using the older three-evaluator preset. The current preset additionally checks `security_flag` and `missing_fields` against dataset labels. The earlier 14/14 candidate result does not include those new checks; the corrected five-metric run above does.

The five-metric runs revealed that invalid and blank PDF cases were labeled with `missing_fields: []`. These were reviewed and corrected, and the Coordinator's invalid-PDF email fallback was made consistent with its blank-PDF path. The screenshot of the corrected run still displays dataset version `1.0.0`; update the Internship manifest version before treating subsequent runs as a new versioned baseline. Reports already saved as 1.0.0 retain that version, even if their underlying labels differed. Do not compare runs across that label change as if they used identical inputs.

The ATA-RAG semantic judge marked all three facts as matched after provider credentials were fixed. Judge scores depend on provider and model; three cases do not establish agreement with human reviewers. Application token/cost totals in a report exclude judge token usage stored in `semantic_facts` result metadata.

## Requirements still open

| Requirement | Current state | Next work |
| --- | --- | --- |
| At least 100 ATA-RAG and 50 Internship cases | 3 and 14 | Curate cases, review labels, version and release datasets with checksums |
| Human reviews tied to cases and Langfuse traces | Case review UI/API and separate JSON records implemented; no trace linkage | Collect human reviews and publish linked scores |
| Validate LLM judge against humans | No judge versus human comparison | Collect independent reviews and measure agreement by category |
| At least five evaluators per system | Both dashboard presets have five; the five-metric Internship run passed 14/14 after two labels were corrected | Review labels independently on a larger set |
| Langfuse dataset/experiment workflow | Observations and scores published when configured; no dataset synchronization | Upload datasets, link traces to dataset items, verify in Langfuse |
| CI regression gate with demonstrated failure | Local tests and comparison API exist; no checked-in CI gate | Run offline tests in CI and demonstrate a deliberate regression with its trace |

Version the corrected Internship dataset, then collect human reviews and expand the reviewed datasets. A perfect score on 14 cases does not establish performance outside those cases.
