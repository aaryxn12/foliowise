# FolioWise Roadmap

Goals-based mutual fund planning agent. This file tracks build progress, milestone by milestone.
Estimates are focused hours. Status key: `[x]` done, `[ ]` to do.

## Progress at a glance

| # | Milestone | Status | Est. hours left |
|---|---|---|---|
| 1 | Maths engine (`planner/sip.py`) | Done | 0 |
| 2 | Investment policy and allocation (`planner/allocation.py`) | Done | 0 |
| 3 | Fund data and screening | In progress | 5 |
| 4 | Plan builder (form in, full plan out) | Not started | 3 |
| 5 | Agent (LangGraph) | Not started | 7 |
| 6 | Fund Q&A with RAG | Not started | 4 |
| 7 | Evals | Not started | 4 |
| 8 | API (FastAPI) | Not started | 3 |
| 9 | AWS deploy (CDK) and CI/CD | Not started | 6 |
| 10 | Frontend (Angular) | Not started | 8 |
| 11 | Launch polish | Not started | 3 |
| | **Total remaining** | | **~42** |

---

## 1. Maths engine
Pure time-value-of-money functions, test-first.

- [x] `annual_to_monthly_rate` (effective, not r/12)
- [x] `future_cost`, `future_value_lumpsum`, `lumpsum_needed`
- [x] `sip_needed` returning `GoalFunding` (annuity due, existing lumpsum, surplus)
- [x] `retirement_corpus` (year-by-year sum; handles return == inflation)
- [x] `check_affordability` returning `Affordability`
- [x] 16 tests incl. month-by-month simulation and closed-form cross-check
- Test count after milestone 2: 78
- [x] Commit and push; Ruff format + check clean

## 2. Investment policy and allocation
Turn the CFA policy tables into config plus code that applies them.

- [x] `RiskLevel` ordered Enum
- [x] Willingness score from the 4 behaviour questions in the quiz
- [x] Ability score (emergency fund, dependents without second income, EMI burden; horizon applied per goal instead)
- [x] `risk_bucket` = lower of willingness and ability
- [x] Policy table as constants in `allocation.py` (equity by band + gold)
- [x] Equity split by bucket (large/flexi/mid/small) and default asset-class return assumptions
- [x] `goal_allocation` with glide path (per goal)
- [x] `expected_return` per goal from its mix
- [x] Existing investments grown at type-specific rates (MF, FD, PPF, EPF)
- [x] Emergency fund check (6 x monthly outgoings)
- [x] Crash test (illustrative severe crash) on a given amount and allocation

## 3. Fund data and screening
- [x] Fund universe: every eligible direct-growth fund per category (AMFI categories, 5+ yrs history) via `scripts/fetch_funds.py`: 111 funds (index 15, flexi 27, mid 21, small 22, debt 17, gold 9)
- [x] NAV history download (mfapi.in), same script; ~14 MB, gitignored
- [ ] Metrics from NAV history: rolling 5-yr consistency vs index, Sharpe, max drawdown
- [ ] Expense ratios merged in from AMFI TER disclosure (minimum-AUM filter optional)
- [ ] Filters + weighted percentile score; top pick + 2 alternatives per category
- [ ] Rupee split: round to Rs500, exact total, minimum SIPs, fund count scales with SIP size
- [ ] Data refresh script that writes a metrics file (nightly schedule comes in milestone 9)

## 4. Plan builder
- [ ] Input model for the full form (Pydantic) with validation (e.g. expenses > take-home)
- [ ] Orchestrate: form → goals → corpus → allocation → SIP per goal → affordability → funds → plan JSON
- [ ] Shortfall levers: retire later, smaller goal, step-up SIP, use lumpsum
- [ ] Plan versioning (previous snapshot for "was X" and Undo)

## 5. Agent (LangGraph)
- [ ] Graph state schema (profile, plan, plan history, chat)
- [ ] Engine functions wrapped as tools (docstrings become tool descriptions)
- [ ] Router: calculation tool vs fund Q&A vs refuse (e.g. "guaranteed 15%?")
- [ ] What-if node: extract the change, re-run the plan, return old vs new
- [ ] Free-text "anything else?" → structured constraints
- [ ] DynamoDB checkpointer (DynamoDB Local first), session TTL
- [ ] Model swap via LangChain config (Groq dev, Claude/Bedrock prod)

## 6. Fund Q&A with RAG
- [ ] Collect scheme documents and factsheets for the curated funds
- [ ] Chunk + embed (choose embedding approach with cold start in mind)
- [ ] FAISS index file, stored in S3
- [ ] Retriever with fund-name filtering; answers cite the document and date

## 7. Evals
- [ ] Small reusable eval harness (reused in projects 2 and 3)
- [ ] Numeric accuracy: agent answers match engine output
- [ ] Routing accuracy on a question set
- [ ] Safety: never promises returns, refuses prohibited advice
- [ ] Constraint extraction accuracy
- [ ] RAG grounding (LLM-as-judge)

## 8. API (FastAPI)
- [ ] Endpoints: create session, generate plan, chat (streaming)
- [ ] Pydantic request/response models shared with the plan builder
- [ ] Anonymous session ID handling; per-IP rate limit and max turns
- [ ] Dockerfile with Lambda Web Adapter; runs locally with uvicorn

## 9. AWS deploy (CDK) and CI/CD
- [ ] Spike: hello-world FastAPI streaming through CloudFront → Lambda Function URL (do early)
- [ ] CDK stacks: S3 + CloudFront (OAC, SPA CloudFront Function), Lambda container, DynamoDB with TTL
- [ ] EventBridge nightly data refresh Lambda
- [ ] Budget alarm, rate limiting (WAF or DynamoDB counter), reserved concurrency
- [ ] GitHub Actions: tests + Ruff on every push; deploy on main via OIDC
- [ ] Production model access (fix expired card, retry Bedrock; else Anthropic API)

## 10. Frontend (Angular)
- [ ] Scaffold; port Nocturne tokens from `design/` into global styles
- [ ] Landing page
- [ ] 5-step form with validation and review page
- [ ] Dashboard: summary cards, goal cards, allocation donut, corpus chart, fund cards, crash test, assumptions sliders
- [ ] Shortfall state with levers; emergency-fund warning
- [ ] Chat panel with streaming, source tags, "Plan updated" + Undo
- [ ] SHA-256 body hash interceptor (CloudFront OAC requirement)
- [ ] Mobile layout (chat bottom sheet); loading, error and empty states
- [ ] Download plan (PDF)

## 11. Launch polish
- [ ] README: architecture diagram, design decisions, how the evals work, screenshots
- [ ] Demo GIF or short video
- [ ] Interview question bank for this project + mock interview
- [ ] Add to resume and portfolio site

---

## Scope decision
2026-11-22: building the full scope (no v1 cut), with more weekly time on the project.
