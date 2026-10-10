# CAL-QG — Calibrated, evidence-Anchored, failure-Learning Question Generation

Python AI/RAG service implementing the curriculum-grounded multi-agent question
generation and validation framework (Fig. 1). Runs fully offline out of the box
(mock LLM + TF-IDF embeddings); add an API key for real generation.

## Quick start
```bash
python -m pip install -r requirements.txt
python -m pytest -q tests               # 5 tests
uvicorn calqg.api:app --port 8000       # REST service for the Node.js backend
```
Real LLM: `export GEMINI_API_KEY=...` (or `OPENAI_API_KEY`). Optional upgrades are
auto-detected: `sentence-transformers` (neural embeddings), `qdrant-client`.

## What is novel (claimable contributions)
1. **Evidence-anchored deterministic validation.** The generator must return a verbatim
   evidence span. Answerability and grounding are verified *against the retrieved source*
   (span matching + content-token recall), not by an LLM grading its own output. This removes
   the self-evaluation bias of LLM-as-judge pipelines for the two most critical criteria, which
   are also *hard gates* (a high weighted score cannot compensate for an ungrounded question).
2. **Failure-memory guided regeneration.** Validators emit typed failure codes
   (`UNGROUNDED`, `BLOOM_MISMATCH`, ...). These become targeted repair constraints for the
   failing question, and codes recurring across the batch are promoted to *global* constraints
   injected pre-emptively into later prompts, so the system learns from its own mistakes within a batch.
3. **IRT-calibrated difficulty.** Instead of an LLM guessing Easy/Medium/Hard, a Rasch model is
   fitted to real student responses, and a regressor maps question features to item difficulty
   so new, unanswered questions get calibrated estimates (`POST /calibrate`).
4. **Coverage-aware planning across batches.** The planner allocates Bloom levels by
   largest-remainder over a target mix, and concepts by coverage deficit over the persistent
   question bank, so repeated generation keeps covering the syllabus instead of repeating topics.

Design principle: **agents generate and repair, validators only judge** — which gives each
agent a distinct, ablatable role.

## Architecture mapping
| Fig. 1 stage | File |
|---|---|
| 1. PDF processing, semantic chunking, concept mapping | `calqg/ingest.py`, `embeddings.py`, `vectorstore.py` |
| 2. Student / task profile | `Profile` in `calqg/api.py` |
| 3. Planner, Retriever (MMR), Generator, Bloom, Difficulty, Fact-check, Diversity agents | `calqg/agents.py`, `llm.py` |
| 4. Seven validators, quality score, threshold loop, Regeneration agent | `calqg/validators.py`, `failure_memory.py`, `pipeline.py` (LangGraph) |
| 5. Final output (question, Bloom, difficulty, source, topic, type) | `CALQG._finalise` |
| 6. Auto metrics, human-rating export, Cohen's kappa, ablation, Wilcoxon | `calqg/evaluation.py` |

## REST API (for the Node.js / Express backend)
- `POST /ingest` (multipart: `file`, `concepts`) — PDF or markdown syllabus unit
- `POST /generate` (JSON profile: `num_questions`, `concepts`, `bloom_levels`, `difficulty`, `question_type`)
- `POST /calibrate` (JSON: `question_ids`, `responses` students x items, 1/0/null)
- `GET /health`

Express proxy example:
```js
app.post("/api/generate", async (req, res) => {
  const r = await fetch("http://localhost:8000/generate", {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(req.body)});
  const data = await r.json();
  await Question.insertMany(data.questions);          // MongoDB
  res.json(data);
});
```
Real LLM generation with retries takes tens of seconds per batch: in production put
`/generate` behind a job queue (BullMQ or Celery + Redis) rather than a blocking request.

## Important limitations (read before writing results)
- **The mock LLM is a test harness, not a generator.** It deliberately injects realistic
  errors (wrong Bloom verb, paraphrased evidence) to exercise the loop. Ablation numbers printed
  by `run_demo.py` only show the pipeline works; **publishable results must come from runs with
  Gemini/OpenAI and expert ratings.**
- The IRT demo uses **synthetic students**. Replace with real class responses (e.g. quiz results).
  Calibration needs a reasonable item bank (dozens of items); with ~10 items it underperforms the prior.
- The rule-based Bloom classifier and grammar check are baselines; a fine-tuned BERT Bloom
  classifier would strengthen the paper.
- Grounding uses lexical span matching. It is strict and transparent but will reject legitimate
  multi-sentence synthesis; an NLI entailment model is a natural extension.

## Suggested experiments for the paper
1. Baseline: single-prompt 8-shot generation vs CAL-QG (same LLM, same chunks).
2. Ablations: `use_failure_memory`, `use_coverage_planner`, `use_irt_calibration`, and each validator
   via `disabled_validators` — report acceptance, LLM calls/question, coverage, ungrounded rate.
3. Human evaluation: `human_rating_sheet.csv` to 3+ faculty, 200–500 questions; report
   Cohen's/Fleiss' kappa and auto-vs-human correlation (`human_agreement`).
4. Difficulty validity: correlation of predicted vs IRT difficulty on held-out items from real tests.
