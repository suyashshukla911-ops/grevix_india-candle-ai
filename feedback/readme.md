India Candle AI — TrustGraph
AI-assisted market analysis with model validation, risk context, and environment-aware trust.





Live Demo
India Candle AI: https://india-candle-ai-aftercode.onrender.com/
The competition deployment is designed to run without requiring a user to configure market-data or GitHub API credentials before trying the application. Live provider integrations can be enabled later through the provider boundary.
What is India Candle AI?
India Candle AI is an AI-assisted short-term stock-analysis platform for Indian equities.
The original product problem was:
How can market data and machine learning be combined into a more disciplined short-term market-analysis workflow instead of relying only on intuition?

The platform combines historical OHLCV data, technical feature engineering, model validation, market-regime context, explainability, risk information, and signal gating to produce:
- next-close / next-range estimates
- BUY / SELL / NO-TRADE decisions
- model validation metrics
- selective signal precision
- confidence and risk context
- multi-timeframe candle analysis
- signal history and audit information
The system is designed as a decision-support prototype, not a guarantee of future returns.
Why the project changed for AfterCode
The first AfterCode challenge introduced the Missing Update Window problem.
A market prediction is produced by software, and that software is not static. Source code, feature engineering, dependencies, configuration, and security state can change after a prediction has been generated.
That creates a second question beyond:
“What does the model predict?”

India Candle AI now also asks:
“Can I still trust the environment that produced that prediction?”

To solve this, the project adds TrustGraph.
TrustGraph
TrustGraph connects market evidence and software-environment evidence into one trust workflow.
                   TRUSTGRAPH
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
  MARKET DATA        MODEL          REPOSITORY
   FRESHNESS       VALIDATION        FRESHNESS
       │               │                │
       └───────────────┼────────────────┘
                       ▼
                 TRUST ENGINE
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
      TRUSTED       NO-TRADE      REVALIDATE
      BUY/SELL     gate failed     environment
Repository lifecycle
CURRENT
   │
   │ repository / dependency change
   ▼
STALE
   │
   │ review + fresh scan
   ▼
REVALIDATE
   │
   │ accept new baseline
   ▼
CURRENT
The important design principle is:
Detect automatically. Trust explicitly.

A changed repository is detected automatically, but the new state is not silently promoted to a trusted baseline.
What TrustGraph monitors
TrustGraph can monitor a local project or a public GitHub repository and track:
- added files
- modified files
- removed files
- dependency-file changes
- source/configuration changes
- security findings
- code-quality findings
- component-level fingerprints
- change impact and revalidation scope
- accepted-baseline history
A monitored repository does not have to be a stock-market project. It can be a Python application, web application, API, LMS, cybersecurity project, or another public software repository.
For public GitHub repositories, the workflow is:
GitHub repository URL
        ↓
Clone / monitor
        ↓
Create fingerprint + manifest
        ↓
Accept baseline
        ↓
Check again later
        ↓
Detect changes
        ↓
Estimate impact
        ↓
Require revalidation when appropriate
Machine Learning
The market-analysis layer uses time-series feature engineering and time-ordered validation rather than randomly shuffling financial observations.
The feature layer can incorporate signals such as:
- EMA structure
- RSI
- ATR / volatility
- MACD
- Bollinger position
- momentum
- volume behaviour
- VWAP-related context
- session/time features
- market-regime information
The model layer uses deterministic, cacheable estimators so repeated analysis for the same stock/timeframe does not require unnecessary retraining.
90% signal gate
The application does not claim that every stock or timeframe is 90% directionally accurate.
Instead, the product uses a selective signal-precision gate:
Validation precision >= configured 90% threshold
                    ↓
            BUY / SELL may be trusted
If the validation evidence does not support the threshold:
NO-TRADE
This allows the system to abstain instead of manufacturing confidence.
The threshold-selection objective is:
Maximize signal coverage
subject to
validation signal precision >= 90%
Market regime and explainability
The prediction layer also evaluates market context such as:
- trending conditions
- sideways conditions
- volatility regime
- momentum
- volume behaviour
The dashboard exposes a Why This Signal? section so a BUY/SELL/NO-TRADE decision is not presented as a black box.
Example structure:
BUY

Supporting factors
✓ Momentum confirmation
✓ EMA structure
✓ RSI / trend confirmation

Risk factors
⚠ Elevated volatility
⚠ Conflicting market context
Backtesting and signal history
The platform is designed to evaluate model behaviour historically instead of showing only a single prediction.
The analysis layer can report metrics such as:
- directional accuracy
- signal precision
- signal coverage
- validation rows
- MAE / prediction error where applicable
- winning / losing signals
- return comparison
- drawdown
- buy-and-hold comparison
The Signal Journal provides a chronological record of generated signals and their associated model/environment context.
Environment-aware trust decision
The final decision is not based on model probability alone.
A simplified trust condition is:
                    ┌────────────────────┐
                    │ Repository current │
                    └─────────┬──────────┘
                              │
                              +
                              │
                    ┌─────────▼──────────┐
                    │ Model gate passes │
                    │   (>= 90% signal  │
                    │      precision)   │
                    └─────────┬──────────┘
                              │
                              +
                              │
                    ┌─────────▼──────────┐
                    │ Data/current state │
                    │     acceptable     │
                    └─────────┬──────────┘
                              │
                              ▼
                       TRUSTED SIGNAL
                       BUY / SELL
If the repository is stale:
REVALIDATE
If the model gate is not satisfied:
NO-TRADE
Challenge Card 1 — The Missing Update Window
The adaptation directly addresses the challenge by preventing an old scan or prediction environment from being silently treated as current.
Proof-of-concept flow
1. Scan + accept baseline
2. Repository = CURRENT
3. Simulate an overnight code/dependency change
4. Detect changed files
5. Detect dependency change
6. Mark repository = STALE
7. Prediction trust = REVALIDATE
8. Scan and accept the new baseline
9. Repository = CURRENT
10. Generate a fresh trusted analysis
Challenge Card 2 — Real-World Feedback
For the second challenge, the product is being put in front of real users and peers for direct criticism.
Feedback evidence is stored under:
/feedback/
The feedback record should contain:
- screenshot of the public post or community message
- screenshots of genuine user responses
- the key problem users identified
- the product change made because of that feedback
- before / after screenshots
See:
[`feedback/README.md`](./feedback/README.md)
Example feedback-driven improvement
One of the targeted usability questions is whether users understand why a prediction can move to REVALIDATE.
The intended UX explanation is:
Repository changed
        ↓
The environment that produced the previous result changed
        ↓
Previous trust state becomes stale
        ↓
Fresh validation is required
This turns a technically correct state transition into an understandable user action.
Technology Stack
Backend
- Python
- FastAPI
- Uvicorn
- Pydantic
Machine Learning
- NumPy / Pandas-style feature processing
- scikit-learn-compatible estimators
- time-ordered validation
- model caching / persistence
- deterministic signal gating
Market Data
- Yahoo Finance provider for live market data when available
- provider boundary for adding other live market sources later
- local deterministic data path for reproducible competition operation where configured
Trust / Security
- SHA-256 fingerprints
- component-level manifests
- dependency-change detection
- security/code-quality scanning
- audit history
- revalidation state machine
Frontend
- HTML
- CSS
- JavaScript
- responsive light-theme dashboard
- local chart rendering without requiring a third-party chart CDN
Running locally
1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1
2. Install dependencies
python -m pip install -r requirements.txt
3. Configure environment variables
Copy the example environment file:
copy .env.example .env
Do not commit secrets to GitHub.
4. Start the application
python -m uvicorn app.main:app
Then open:
http://127.0.0.1:8000
For the competition demonstration, run without --reload so the mutable monitored repository does not trigger development-server reloads.
Recommended demonstration sequence
Part 1 — Core product
1. Open Market Predictor.
2. Select a stock and timeframe.
3. Run analysis.
4. Show next-move estimates, signal, validation, explainability, and risk context.
Part 2 — TrustGraph
1. Open TrustGraph / Repository Health.
2. Scan and accept the baseline.
3. Show CURRENT.
4. Simulate or manually introduce a repository change.
5. Check for updates.
6. Show STALE, changed files, dependency changes, and impact.
7. Return to Market Predictor.
8. Show REVALIDATE.
9. Accept a fresh baseline.
10. Show CURRENT and run a fresh analysis.
Part 3 — Generic repository monitoring
1. Paste a public GitHub repository URL.
2. Clone & Monitor.
3. Scan and accept the baseline.
4. Make or wait for a repository change.
5. Check for updates.
6. Review change impact, dependencies, security findings, and required revalidation.
Engineering principles
1. Do not silently claim confidence
The system should abstain when evidence is insufficient.
2. Keep detection and trust acceptance separate
A change can be detected automatically while still requiring explicit revalidation.
3. Preserve auditability
Older baselines and findings should remain visible rather than being silently overwritten.
4. Keep providers replaceable
Market-data and GitHub providers are separated from the trust state machine so live integrations can be upgraded without rewriting the dashboard architecture.
5. Prefer reproducibility during judging
The competition build should remain runnable without requiring an evaluator to configure private credentials first.
Testing
Run the test suite with:
pytest -q
The test suite covers the market pipeline, API behaviour, repository fingerprinting, change detection, stale/revalidation logic, dependency changes, security checks, and end-to-end trust transitions.
Limitations and responsible use
India Candle AI is a prototype / decision-support system, not a guarantee of investment returns.
Important limitations include:
- market data availability varies by provider, symbol, exchange, and timeframe
- not every listed security will necessarily have historical intraday data available from Yahoo Finance
- model performance can change as market regimes change
- a 90% precision gate applies to qualifying signals under the validation procedure; it is not a promise of 90% live-market accuracy
- repository/security checks are lightweight application-level checks, not a complete enterprise SAST/SCA platform
Always validate data, model performance, and risk assumptions before using the system for real financial decisions.
Roadmap
Planned production integrations include:
- authenticated live market-data providers
- automated GitHub webhook-driven repository refresh
- persistent database-backed audit storage
- user authentication and role-based access
- deeper dependency vulnerability analysis
- enterprise-grade SAST/SCA integrations
- richer model monitoring and drift detection
Project structure
india-candle-ai/
├── app/                    # FastAPI backend and services
├── frontend/               # dashboard assets
├── tests/                  # automated tests
├── workspace/              # monitored repository workspace
├── runtime/                # runtime/cache data
├── feedback/               # Challenge Card 2 evidence
├── legacy_original/        # preserved original implementation/reference
├── ARCHITECTURE.md         # system architecture
├── CHALLENGE_MAPPING.md   # AfterCode challenge mapping
├── MODEL_POLICY.md        # model / signal policy
├── JUDGING.md              # judging workflow
├── RUNBOOK.md              # operations / demo runbook
├── START_HERE.md           # quick-start guide
├── FINAL_TEST_REPORT.md   # verification results
├── .env.example            # safe environment template
└── requirements.txt        # Python dependencies
AfterCode submission
Project: India Candle AI — TrustGraph
AfterCode Challenge 1: The Missing Update Window
AfterCode Challenge 2: Real-World Feedback
Live Demo:
https://india-candle-ai-aftercode.onrender.com/
GitHub:
https://github.com/suyashshukla911-ops/grevix_india-candle-ai