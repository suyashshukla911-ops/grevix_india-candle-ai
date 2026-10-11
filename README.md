# India Candle AI

A web version of the original Tkinter stock predictor, rebuilt around exchange/broker market data instead of Yahoo/stooq scraping.

## What changed

The old program predicted the **next trading day's close** from daily candles and used a keyword sentiment score. This version is designed for the actual product requirement:

`Upstox market data -> session-aware features -> walk-forward ML -> next candle OHLC scenario + EOD scenario -> news/event layer -> gated signal`

It is India-only and can search the NSE/BSE equity universe from Upstox's daily instrument files.

## Priority universe

The dashboard prioritizes:

- United Spirits
- Sula Vineyards
- Globus Spirits
- Radico Khaitan
- Cupid
- Meesho
- Raymond
- Kalyan Jewellers
- Orient Electric
- MRF
- Tata Motors
- HDFC Bank

The resolver does not hard-code instrument keys. It refreshes the NSE/BSE instrument master and resolves the current instrument key by trading symbol/name, so exchange changes and new listings can be handled without editing the code.

## Candle logic

The UI supports 1, 2, 3, 5, 10, 15, 30 and 60 minute views. Upstox V3 supports minute intervals from 1 through 300, so the code can accept any value 1..300.

The model produces:

- next-candle close
- next-candle high scenario
- next-candle low scenario
- same-session end-of-day close scenario
- probability of up/down
- a BUY / SELL / NO-TRADE gate

The EOD scenario is recalculated from the current intraday state; it does not assume the next session opens at today's close.

## News engine

The default news source is GDELT DOC 2.0. It returns recent article metadata such as title, URL, domain, and timestamp. The engine adds:

- lexical financial sentiment
- event class
- source quality
- recency decay
- capped news impact

The browser shows a link back to the original article. For commercial use, keep the news provider and content licensing aligned with the provider's terms. Times of India's RSS terms, for example, restrict commercial reuse, so this build does **not** make TOI the default feed.

## ML design

The model is intentionally not a single regression formula.

1. Technical/session feature engine:
   - multi-horizon returns
   - candle body/range/wicks
   - ATR and RSI
   - EMA gaps and spread
   - rolling volatility
   - volume z-score
   - session VWAP gap
   - time-of-day cyclic features
   - day-of-week cyclic features
   - overnight session gap
   - distance from session high/low
   - NIFTY / BANKNIFTY / INDIA VIX context returns

2. Direction model:
   - HistGradientBoostingClassifier
   - RandomForestClassifier
   - ExtraTreesClassifier

3. Price-path regressors:
   - HistGradientBoostingRegressor
   - RandomForestRegressor
   - ExtraTreesRegressor

4. Validation:
   - chronological holdout
   - no shuffling
   - signal threshold chosen from the validation set
   - BUY/SELL can be suppressed when validation evidence is weak or current news conflicts

The website shows **measured validation accuracy/precision**, not a fabricated 100% claim. Markets are stochastic and a guaranteed 100% future hit rate is not technically defensible.

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

### Upstox connection

Create an Upstox developer app and register your exact callback URL, e.g.:

`http://localhost:8000/auth/upstox/callback`

Set:

```text
UPSTOX_CLIENT_ID=...
UPSTOX_CLIENT_SECRET=...
UPSTOX_REDIRECT_URI=http://localhost:8000/auth/upstox/callback
```

The homepage has a **Connect Upstox** button.

For a read-only personal prototype, Upstox now also provides an **Analytics Token** with 1-year validity and access to market-data, historical-data, option-chain, market-information, news, and WebSocket categories. That is the easiest first setup because it avoids daily OAuth during local testing.

Set `UPSTOX_ACCESS_TOKEN` in `.env` with that token. Do not put credentials in Git.

## Deployment

The repo contains both `Dockerfile` and `render.yaml`.

A simple path is:

1. Push this folder to GitHub.
2. Deploy it as a Render web service.
3. Add the Upstox secrets in Render environment variables.
4. Register the deployed callback URL in Upstox.
5. Open the site and connect Upstox.

## Important product limitation

The free/current architecture is optimized for a **watched stock dashboard plus an all-NSE/BSE searchable universe**. It does not try to train every Indian stock every minute. That would be wasteful.

For a later scanner, use Upstox full market quotes in batches (up to 500 instrument keys per request) to rank the complete universe, and only run expensive candle models on the top candidates.

## References

Upstox:
- https://upstox.com/developer/api-documentation/v3/get-intra-day-candle-data/
- https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/
- https://upstox.com/developer/api-documentation/v3/get-market-data-feed/
- https://upstox.com/developer/api-documentation/get-full-market-quote-v3/
- https://upstox.com/developer/api-documentation/instruments/
- https://upstox.com/developer/api-documentation/authentication/

NSE:
- https://www.nseindia.com/static/market-data/market-timings

News:
- https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- https://timesofindia.indiatimes.com/fcom/rss.cms

## Disclaimer

This is an analytical/paper-trading system. It does not place orders and does not guarantee profits or prediction accuracy.
