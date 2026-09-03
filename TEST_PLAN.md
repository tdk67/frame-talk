# Test Plan & Evaluation Protocol: Frame Talk

This document defines the formal Evaluation Framework (Evals) and End-to-End Verification Protocol for **Frame Talk** (formerly CastOps AI) prior to full hackathon deployment.

---

## 🎯 Strategic Objectives & Value Proposition

**Core Problem:** Traditional automated video walkthrough tools and audio generators suffer from:
1. **Blind Audio (e.g. NotebookLM):** Can generate audio podcasts from text/notes or transcripts, but cannot visually ingest, inspect, or synchronize with an unedited silent application screencast (`.mp4`).
2. **Timing Desynchronization:** Audio either outpaces the screen or lags behind, talking about past screens or premature future screens.
3. **Rigid Ping-Pong Monologues:** 5-10 second artificial silence buffers inserted to force audio into guessed timestamps.

**Frame Talk Solution:**
1. **Vision-Grounded:** Uses **`gemini-3.7-flash`** to analyze actual video pixels across time.
2. **Millisecond Synchronized:** Uses **`gemini-3.1-flash-tts-preview`** raw PCM output to calculate exact audio duration down to the millisecond.
3. **Chronos Dynamic Visual Hold:** Injects calculated frame freezes (`required_freeze_ms`) to stretch the video timeline when explanations run deep, completely eliminating lag and silence padding.

---

## 🔬 Multi-Stage Decoupled Evaluation Protocol (Evals)

Frame Talk uses a **four-stage decoupled evaluation architecture** with a predefined ground-truth dataset (`server/evals/dataset/`):
* `server/evals/dataset/expected_scenes.json`: 9-scene gold-standard ground truth extracted from the reference screencast.
* `server/evals/dataset/expected_dialogue.json`: High-cadence reference dialogue between Alex and Sarah.
* `server/evals/dataset/sample_readme.md`: Idea Lint architecture documentation.

---

### Stage 1: Video Analyzer Evaluation (Dataset Grounding & Precision)
* **Evaluator Script:** [`server/evals/eval_1_video_analyzer.py`](server/evals/eval_1_video_analyzer.py)
* **Objective:** Compares generated scene decomposition against the predefined ground-truth dataset.
* **CLI Command:** `python -m server.evals.eval_1_video_analyzer --benchmark`

| Eval Metric | Target | Measurement Method | Strict Failure Criteria |
| :--- | :--- | :--- | :--- |
| **Ground-Truth Entity Recall** | $\ge 70\%$ | Measures recall of 61 concrete visual entities from expected scenes (*"Idea Lint"*, *"BYOK"*, *"Song Blueprint Analyser"*, *"VentureBot"*, *"Cyanite"*, *"Tunebat"*, *"Doomsday Clock"*). | Missing critical named UI entities. |
| **Action-Reaction Causality** | $\ge 85\%$ | Validates direct causal pairing between physical user action (`user_action`) and visible screen reaction (`app_reaction`). | Missing user input or tautological descriptions. |
| **Anti-Generic Blacklist** | **0 hits** | Scans all fields against filler phrases (*"Navigating interface"*, *"Real-time rendering"*, *"State transition update"*). | **Any single boilerplate match fails immediately.** |
| **Overall Stage 1 Score** | $\ge 80/100$ | Weighted composite: Entity Recall (45%) + Causality (35%) + Scene Count (20%). | Score $< 80$ or any boilerplate detected. |

---

### Stage 2: Dialogue Script Generation Evaluation (Visuals + README)
* **Evaluator Script:** [`server/evals/eval_2_dialogue_script.py`](server/evals/eval_2_dialogue_script.py)
* **Objective:** Evaluates dialogue generation given known visual scenes and README documentation.
* **CLI Command:** `python -m server.evals.eval_2_dialogue_script --benchmark`

| Eval Metric | Target | Measurement Method | Strict Failure Criteria |
| :--- | :--- | :--- | :--- |
| **Visual Scene Anchoring** | $\ge 85\%$ | Validates that dialogue turns in Scene $N$ discuss observed elements in Scene $N$. | Talking about a modal or feature before it appears. |
| **README Concepts Grounding** | $\ge 80\%$ | Verifies coverage of architecture concepts (*courtroom*, *adversarial*, *byok*, *privacy*, *decision gate*). | Omission of core technical principles. |
| **Anti-Timestamp Constraint** | **100% Pass** | Regex scan for explicit time utterances (`\b\d{1,2}:\d{2}\b`, *"at 0:15"*, *"at 1 minute"*). | Any spoken explicit timestamp reference. |
| **Conversational Cadence** | $\ge 90\%$ | Turn-taking alternation ratio and speaker balance between Alex and Sarah. | Monologues or consecutive turns by the same speaker. |
| **Overall Stage 2 Score** | $\ge 80/100$ | Weighted composite: Anchoring (35%) + README (30%) + Cadence (20%) + Anti-Timestamp (15%). | Score $< 80$ or any timestamp uttered. |

---

### Stage 3: QA & Pacing Auditor Evaluation (Sensitivity & Discrimination)
* **Evaluator Script:** [`server/evals/eval_3_qa_auditor.py`](server/evals/eval_3_qa_auditor.py)
* **Objective:** Evaluates the QA Agent itself via dual benchmark batteries (positive verification + defect injection).
* **CLI Command:** `python -m server.evals.eval_3_qa_auditor`

| Eval Battery | Target | Measurement Method | Failure Criteria |
| :--- | :--- | :--- | :--- |
| **Battery 1: Positive Benchmark** | $\ge 85/100$ | Given gold-standard dialogue and scenes, verifies QA produces high scores across accuracy, README alignment, and pacing. | False negative rejection of high-quality script. |
| **Battery 2: Defect Injection** | **100% Detected** | Injects deliberate defects (robotic timestamp *"At 0:15"*, off-topic pizza hallucination) and checks if QA catches them. | False positive acceptance of defective dialogue. |
| **Overall Auditor Score** | $100/100$ | Dual-battery verification: Positive Pass (50 pts) + Defect Caught (50 pts). | Failure on either battery. |

---

### Stage 4: Google Cloud Agent Platform Director Evaluation (ADK & Guardrails)
* **Evaluator Script:** [`server/evals/eval_4_gcp_director.py`](server/evals/eval_4_gcp_director.py)
* **Objective:** Validates `agent.py` running on Google ADK v2.7.1, anti-prompt injection scope lock, and Chronos dynamic hold calculations.
* **CLI Command:** `python -m server.evals.eval_4_gcp_director`

| Eval Metric | Target | Measurement Method | Failure Criteria |
| :--- | :--- | :--- | :--- |
| **ADK Export Integrity** | $100\%$ | Verifies `root_agent` export and subagent bindings in ADK. | Missing `root_agent` or broken persona agents. |
| **Anti-Injection Refusal** | $100\%$ | Injects jailbreak prompts; verifies `ACCESS DENIED` response. | Following adversarial override directives. |
| **Chronos Calculation Math** | $100\%$ | Evaluates freeze hold formulas and $+300\text{ms}$ buffer hold. | Calculation drift or missing hold duration. |
| **Overall Director Score** | $\ge 80/100$ | Composite score across ADK structure, security, and sync. | Score $< 80$. |

---

### 🚀 Master Evaluation Suite Runner
Run all 4 stages consecutively with a unified scorecard:
```bash
python -m server.evals.run_all_evals --all
```

| Eval Metric | Target | Measurement Method | Failure Criteria |
| :--- | :--- | :--- | :--- |
| **Turn-Taking Cadence** | $180\text{ms} - 240\text{ms}$ | Audio silence between alternating speaker turns. | Gaps $> 800\text{ms}$ (dead air) or negative (overlapping speech). |
| **Anti-Timestamp Constraint** | **100% Pass** | Regex scan for explicit time utterances (`\b\d{1,2}:\d{2}\b`, "at 0:14", "at 1 minute"). | Any spoken explicit timestamp reference. |
| **Banter & Chemistry Score** | $\ge 90/100$ | LLM-as-a-Judge audit evaluating natural conversational hooks (*"Right, because..."*, *"Wait, notice how..."*). | Robotic, monotone, or isolated monologues. |

### Tier 4: Telemetry & Observability Evals
* **Objective:** Fulfill ClickHouse + Grafana hackathon partner requirements.

| Eval Metric | Target | Measurement Method |
| :--- | :--- | :--- |
| **ClickHouse Ingestion Rate** | $100\%$ | Every dialogue turn, audio duration, and freeze offset written to `castops.sync_events`. |
| **Grafana Real-time Refresh** | $\le 2\text{s}$ | Live dashboard queries reflecting pipeline runs accurately. |

---

## 🧪 Automated Unit Test Suite (`tests/`)

In addition to LLM model evaluations, Frame Talk includes a fast, zero-dependency unit test suite covering application code, synchronization math, API contracts, security guardrails, repositories, and quotas:

```bash
# Run full unit test suite (51 tests, executes in < 1.5s):
python -m unittest discover tests -v

# Run integrated quality build (HTML lint + unit tests):
npm test
```

| Test Module | Coverage | Status |
| :--- | :--- | :---: |
| [`tests/test_api_routes.py`](tests/test_api_routes.py) | Health, BYOK, security headers (HSTS, CSP), MCP auth & telemetry, non-existent file quota preservation | **19/19 PASS** |
| [`tests/test_chronos_engine.py`](tests/test_chronos_engine.py) | 24 kHz PCM duration math ($48\text{ bytes/ms}$), dynamic freeze calculation, $+300\text{ms}$ buffer | **4/4 PASS** |
| [`tests/test_frontend_html_integrity.py`](tests/test_frontend_html_integrity.py) | LIFO tag stack balancing, illegal nesting blocking, wizard card hierarchy anti-bleed | **2/2 PASS** |
| [`tests/test_quota_service.py`](tests/test_quota_service.py) | Hosted demo key limits (3 videos, $1.00 USD cost cap), IP-bound quota, Global circuit breaker | **8/8 PASS** |
| [`tests/test_repositories.py`](tests/test_repositories.py) | `JobRepository` lifecycle, path traversal blocking, `FileRepository` validation | **5/5 PASS** |
| [`tests/test_security_guardrails.py`](tests/test_security_guardrails.py) | Prompt injection detection, XML isolation wrapping, video magic byte validation | **5/5 PASS** |
| [`tests/test_user_isolation.py`](tests/test_user_isolation.py) | Anonymous client pseudonymization, job ownership isolation, ClickHouse user aggregations | **8/8 PASS** |
| **TOTAL** | **Comprehensive Build Integrity** | **51/51 PASS** |

---

## 📋 End-to-End Functional Test Matrix

| Step | Feature | Test Action | Expected Result | Pass/Fail |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1** | Video Drag & Drop | Drag `.mp4` into dropzone | File metadata (name, size, duration) rendered; left sidebar updated | PASS |
| **Step 1** | README Upload | Drag `.md` into dropzone | File loaded; enables Step 2 CTA button | PASS |
| **Step 2** | `gemini-3.7-flash` Vision | Click "Analyze Video Screen" | Decomposes screencast into chronological Visual Scenes table | PASS |
| **Step 3** | Live Dialogue Script | Click "Draft Live Dialogue" | Generates multi-turn conversation between Alex and Sarah tied to scenes | PASS |
| **Step 3** | Automated QA Audit | Inspect QA Scorecard | Evaluates accuracy, README grounding, and confirms zero timestamps | PASS |
| **Step 4** | Gemini TTS PCM Synthesis | Click "Synthesize & Chronos" | Returns 24kHz raw PCM; calculates exact millisecond duration per line | PASS |
| **Step 4** | Chronos Freeze Offset | Inspect schedule | Computes `required_freeze_ms` whenever speech duration exceeds video scene | PASS |
| **Step 4** | ClickHouse Logging | Inspect database | Micro-events inserted with `audio_duration_ms` and `required_freeze_ms` | PASS |
| **Step 5** | Instant Canvas Preview | Click "Play Interactive Preview" | Canvas holds/freezes video frame during dialogue extensions and unfreezes in sync | PASS |
| **Step 5** | FFmpeg MP4 Compilation | Click "Compile Production MP4" | Stitches final 1080p MP4 with permanent holds and muxed multi-speaker audio | PASS |
