"""
FX Bias Desk — Bloomberg Data Fetcher
======================================
Requires: Bloomberg Terminal open + blpapi installed
Install:  pip install blpapi --index-url https://bcms.bloomberg.com/pip/simple

Run daily via Windows Task Scheduler.
Outputs:  ../data/desk_data.json  (fetched by the desk HTML on load)
          ../data/desk_data.js    (window.DESK_AUTO = {...})
          ../index.html           (copied from template if needed)

After running, git push sends the update to GitHub Pages.
"""

import blpapi
import json, os, sys, time, math
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Bloomberg session
# ─────────────────────────────────────────────────────────────────────────────

def open_session():
    opts = blpapi.SessionOptions()
    opts.setServerHost("localhost")
    opts.setServerPort(8194)
    session = blpapi.Session(opts)
    if not session.start():
        sys.exit("ERROR: Bloomberg session failed — is Terminal open?")
    if not session.openService("//blp/refdata"):
        sys.exit("ERROR: Could not open //blp/refdata service")
    return session

def bdp(session, securities, fields):
    """Bloomberg Data Point — latest value(s) for one or many securities."""
    svc   = session.getService("//blp/refdata")
    req   = svc.createRequest("ReferenceDataRequest")
    if isinstance(securities, str):
        securities = [securities]
    if isinstance(fields, str):
        fields = [fields]
    for s in securities:
        req.append("securities", s)
    for f in fields:
        req.append("fields", f)
    session.sendRequest(req)
    result = {}
    while True:
        ev = session.nextEvent(5000)
        for msg in ev:
            if msg.messageType() == blpapi.Name("ReferenceDataResponse"):
                sd = msg.getElement("securityData")
                for i in range(sd.numValues()):
                    sec  = sd.getValueAsElement(i)
                    name = sec.getElementAsString("security")
                    fds  = sec.getElement("fieldData")
                    result[name] = {}
                    for f in fields:
                        try:
                            result[name][f] = fds.getElementAsFloat(f)
                        except:
                            try:
                                result[name][f] = fds.getElementAsString(f)
                            except:
                                result[name][f] = None
        if ev.eventType() == blpapi.Event.RESPONSE:
            break
    return result

def bdh(session, security, fields, start_date, end_date=None):
    """Bloomberg Data History — daily OHLCV time series."""
    svc = session.getService("//blp/refdata")
    req = svc.createRequest("HistoricalDataRequest")
    req.set("securities", security)
    if isinstance(fields, str):
        fields = [fields]
    for f in fields:
        req.append("fields", f)
    req.set("startDate", start_date.strftime("%Y%m%d"))
    req.set("endDate",   (end_date or date.today()).strftime("%Y%m%d"))
    req.set("periodicitySelection", "DAILY")
    session.sendRequest(req)
    rows = []
    while True:
        ev = session.nextEvent(10000)
        for msg in ev:
            if msg.messageType() == blpapi.Name("HistoricalDataResponse"):
                sd = msg.getElement("securityData")
                fd = sd.getElement("fieldData")
                for i in range(fd.numValues()):
                    row = fd.getValueAsElement(i)
                    entry = {"t": row.getElementAsString("date")}
                    for f in fields:
                        try:   entry[f.lower()] = round(row.getElementAsFloat(f), 5)
                        except: pass
                    rows.append(entry)
        if ev.eventType() == blpapi.Event.RESPONSE:
            break
    return rows

# ─────────────────────────────────────────────────────────────────────────────
# Bloomberg ticker maps
# ─────────────────────────────────────────────────────────────────────────────

FX_TICKERS = {
    "EURUSD": "EURUSD Curncy",
    "GBPUSD": "GBPUSD Curncy",
    "USDJPY": "USDJPY Curncy",
    "AUDUSD": "AUDUSD Curncy",
    "NZDUSD": "NZDUSD Curncy",
    "USDCAD": "USDCAD Curncy",
    "USDCHF": "USDCHF Curncy",
    "USDZAR": "USDZAR Curncy",
    "XAUUSD": "XAUUSD Curncy",
}

Y10_TICKERS = {
    "USD": "USGG10YR Index",
    "GBP": "GUKG10 Index",
    "EUR": "GDBR10 Index",   # Germany Bund (EUR proxy)
    "JPY": "JGBS10 Index",
    "AUD": "GACGB10 Index",
    "NZD": "GNZGB10 Index",
    "CAD": "GCAN10YR Index",
    "CHF": "GSWISS10 Index",
    "ZAR": "GSAB10YR Index",
}

Y2_TICKERS = {
    "USD": "USGG2YR Index",
    "GBP": "GUKG2 Index",
    "EUR": "GDBR2 Index",
    "JPY": "JGBS2 Index",
    "AUD": "GACGB2 Index",
    "NZD": "GNZGB2 Index",
    "CAD": "GCAN2YR Index",
    "CHF": "GSWISS2 Index",
}

RATE_TICKERS = {
    "USD": "FDTR Index",          # Fed Funds Target Rate
    "EUR": "EURR002W Index",      # ECB deposit rate
    "GBP": "UKBRBASE Index",      # BoE Bank Rate
    "JPY": "BOJDPBAL Index",      # BoJ Policy Balance Rate
    "AUD": "RBATCTR Index",       # RBA Cash Rate Target
    "NZD": "RBNZOCR Index",       # RBNZ OCR
    "CAD": "CCLR Index",          # BoC Overnight Rate
    "CHF": "SZLTTR Index",        # SNB Policy Rate
    "ZAR": "SARPRIME Index",      # SARB Repo Rate
}

COT_TICKERS = {
    # CFTC Commitments of Traders — Asset Manager net positions
    "EUR": "FMCCNEUR Index",
    "GBP": "FMCCNGBP Index",
    "JPY": "FMCCNJPY Index",
    "AUD": "FMCCNAUD Index",
    "NZD": "FMCCNNZD Index",
    "CAD": "FMCCNCAD Index",
    "CHF": "FMCCNCHF Index",
}

BRENT_TICKER = "CO1 Comdty"
WTI_TICKER   = "CL1 Comdty"
DXY_TICKER   = "DXY Curncy"

# ─────────────────────────────────────────────────────────────────────────────
# Fetch functions
# ─────────────────────────────────────────────────────────────────────────────

def fetch_yields(session):
    print("Fetching yields...")
    all_tickers = list(Y10_TICKERS.values()) + list(Y2_TICKERS.values())
    data = bdp(session, all_tickers, ["LAST_PRICE"])
    y10, y2 = {}, {}
    for ccy, tk in Y10_TICKERS.items():
        v = data.get(tk, {}).get("LAST_PRICE")
        if v: y10[ccy] = round(float(v), 2)
    for ccy, tk in Y2_TICKERS.items():
        v = data.get(tk, {}).get("LAST_PRICE")
        if v: y2[ccy] = round(float(v), 2)
    print(f"  10Y: {list(y10.keys())}  2Y: {list(y2.keys())}")
    return y10, y2

def fetch_rates(session):
    print("Fetching CB rates...")
    tickers = list(RATE_TICKERS.values())
    data = bdp(session, tickers, ["LAST_PRICE"])
    rates = {}
    for ccy, tk in RATE_TICKERS.items():
        v = data.get(tk, {}).get("LAST_PRICE")
        if v: rates[ccy] = round(float(v), 2)
    print(f"  rates: {rates}")
    return rates

def fetch_spot(session):
    print("Fetching spot prices...")
    tickers = list(FX_TICKERS.values()) + [BRENT_TICKER, WTI_TICKER, DXY_TICKER]
    data = bdp(session, tickers, ["LAST_PRICE"])
    spot = {}
    for pair, tk in FX_TICKERS.items():
        v = data.get(tk, {}).get("LAST_PRICE")
        if v: spot[pair] = round(float(v), 5)
    for label, tk in [("BRENT", BRENT_TICKER), ("WTI", WTI_TICKER), ("DXY", DXY_TICKER)]:
        v = data.get(tk, {}).get("LAST_PRICE")
        if v: spot[label] = round(float(v), 2)
    print(f"  spot: {list(spot.keys())}")
    return spot

def compute_mas(rows, field="px_last"):
    """Compute SMA and EMA for 20/50/100/200 periods."""
    closes = [r[field] for r in rows if r.get(field)]
    if not closes:
        return {}
    def sma(n):
        if len(closes) < n: return None
        return round(sum(closes[-n:]) / n, 5)
    def ema(n):
        if len(closes) < n: return None
        k = 2 / (n + 1)
        e = closes[0]
        for p in closes[1:]:
            e = p * k + e * (1 - k)
        return round(e, 5)
    return {
        "sma20": sma(20),  "sma50": sma(50),
        "sma100": sma(100), "sma200": sma(200),
        "ema20": ema(20),  "ema50": ema(50),
        "ema100": ema(100), "ema200": ema(200),
        "last": closes[-1],
        "count": len(closes),
    }

def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100
    rs = ag / al
    return round(100 - 100 / (1 + rs), 1)

def fetch_history(session, days=750):
    print("Fetching price history...")
    start = date.today() - timedelta(days=days)
    px = {}
    for pair, ticker in FX_TICKERS.items():
        rows = bdh(session, ticker, ["PX_LAST","PX_OPEN","PX_HIGH","PX_LOW"], start)
        if rows:
            # Rename fields to o/h/l/c
            clean = []
            for r in rows:
                clean.append({
                    "t": r["t"],
                    "o": r.get("px_open", r.get("px_last")),
                    "h": r.get("px_high", r.get("px_last")),
                    "l": r.get("px_low",  r.get("px_last")),
                    "c": r.get("px_last"),
                })
            mas = compute_mas(rows)
            closes = [r["c"] for r in clean if r["c"]]
            px[pair] = {
                "rows": clean[-500:],
                "mas":  mas,
                "rsi":  rsi(closes),
                "last": clean[-1]["c"] if clean else None,
            }
            print(f"  {pair}: {len(clean)} rows, RSI={px[pair]['rsi']}")
        time.sleep(0.1)
    # Gold history
    rows = bdh(session, "XAUUSD Curncy", ["PX_LAST","PX_OPEN","PX_HIGH","PX_LOW"], start)
    if rows:
        clean = [{"t":r["t"],"o":r.get("px_open",r.get("px_last")),"h":r.get("px_high",r.get("px_last")),"l":r.get("px_low",r.get("px_last")),"c":r.get("px_last")} for r in rows]
        mas   = compute_mas(rows)
        closes = [r["c"] for r in clean if r["c"]]
        px["XAUUSD"] = {"rows": clean[-500:], "mas": mas, "rsi": rsi(closes), "last": clean[-1]["c"] if clean else None}
    return px

def fetch_cot(session):
    print("Fetching COT data...")
    tickers = list(COT_TICKERS.values())
    # Net position
    data_net  = bdp(session, tickers, ["LAST_PRICE"])
    # Long and short separately where available
    data_long = bdp(session, tickers, ["CFTC_ASSET_MGR_POSITIONS_LONG_ALL"])
    data_shrt = bdp(session, tickers, ["CFTC_ASSET_MGR_POSITIONS_SHORT_ALL"])
    cot = {}
    for ccy, tk in COT_TICKERS.items():
        net   = data_net.get(tk,  {}).get("LAST_PRICE")
        long_ = data_long.get(tk, {}).get("CFTC_ASSET_MGR_POSITIONS_LONG_ALL")
        short = data_shrt.get(tk, {}).get("CFTC_ASSET_MGR_POSITIONS_SHORT_ALL")
        if net is not None:
            total = (long_ or 0) + (short or 0)
            bull  = round(long_ / total * 100, 1) if total and long_ else 50
            cot[ccy] = {
                "net":   int(float(net)),
                "long":  int(float(long_  or 0)),
                "short": int(float(short or 0)),
                "bull":  bull,
            }
    print(f"  COT: {list(cot.keys())}")
    return cot

def fetch_calendar(session):
    """
    Bloomberg ECO calendar — high-impact events next 7 days.
    Uses BDS with EconomicCalendar override.
    """
    print("Fetching economic calendar...")
    events = []
    try:
        svc = session.getService("//blp/refdata")
        req = svc.createRequest("ReferenceDataRequest")
        req.append("securities", "ECWI Index")  # Economic calendar index
        req.append("fields", "ECO_CALENDAR_EVENTS")
        # Date range: today to +7 days
        ov = req.getElement("overrides")
        o1 = ov.appendElement()
        o1.setElement("fieldId", "START_DT")
        o1.setElement("value",   date.today().strftime("%Y%m%d"))
        o2 = ov.appendElement()
        o2.setElement("fieldId", "END_DT")
        o2.setElement("value",   (date.today() + timedelta(days=7)).strftime("%Y%m%d"))
        session.sendRequest(req)
        while True:
            ev = session.nextEvent(5000)
            for msg in ev:
                if msg.messageType() == blpapi.Name("ReferenceDataResponse"):
                    sd = msg.getElement("securityData")
                    for i in range(sd.numValues()):
                        fd = sd.getValueAsElement(i).getElement("fieldData")
                        try:
                            cal = fd.getElement("ECO_CALENDAR_EVENTS")
                            for j in range(cal.numValues()):
                                row = cal.getValueAsElement(j)
                                def gs(name):
                                    try: return row.getElementAsString(name)
                                    except: return ""
                                def gf(name):
                                    try: return row.getElementAsFloat(name)
                                    except: return None
                                imp = gs("IMPORTANCE")
                                if imp in ("HIGH","MEDIUM"):
                                    events.append({
                                        "date":     gs("DATE"),
                                        "time":     gs("TIME"),
                                        "currency": gs("COUNTRY_ISO"),
                                        "event":    gs("NAME"),
                                        "impact":   imp,
                                        "forecast": gs("BN_SURVEY_MEDIAN"),
                                        "previous": gs("PRIOR_VALUE"),
                                        "actual":   gs("ACTUAL_VALUE"),
                                    })
                        except: pass
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
    except Exception as e:
        print(f"  Calendar failed: {e}", file=sys.stderr)
    print(f"  calendar events: {len(events)}")
    return events

# ─────────────────────────────────────────────────────────────────────────────
# CB next meeting dates (static — update after each CB meeting)
# ─────────────────────────────────────────────────────────────────────────────

NEXT_MEETING = {
    "USD": "09/12/2026",   # FOMC
    "EUR": "TBC",
    "GBP": "TBC",
    "JPY": "TBC",
    "AUD": "TBC",
    "NZD": "TBC",
    "CAD": "TBC",
    "CHF": "TBC",
    "ZAR": "TBC",
}

# ─────────────────────────────────────────────────────────────────────────────
# Assemble output + merge with existing hand-edited data
# ─────────────────────────────────────────────────────────────────────────────

def build_output(y10, y2, rates, spot, px, cot, calendar, existing):
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    # MKT.rate — format as ["x.xx%", url] to match desk expectation
    mkt_rate = {}
    for ccy, v in rates.items():
        mkt_rate[ccy] = [f"{v}%", ""]
    # Keep hand-edited rates for currencies Bloomberg didn't return
    for ccy, v in existing.get("MKT", {}).get("rate", {}).items():
        if ccy not in mkt_rate:
            mkt_rate[ccy] = v

    # MKT.y10 / y2 — ["5.12", url]
    mkt_y10 = {c: [str(v), "https://bloomberg.com"] for c, v in y10.items()}
    mkt_y2  = {c: [str(v), "https://bloomberg.com"] for c, v in y2.items()}

    # MKT.cot — [net, bull%, bear%]
    mkt_cot = {}
    for ccy, v in cot.items():
        mkt_cot[ccy] = [v["net"], v["bull"], round(100 - v["bull"], 1)]

    # curve spreads (10Y - 2Y)
    mkt_curve = {}
    for ccy in y10:
        if ccy in y2:
            mkt_curve[ccy] = round(y10[ccy] - y2[ccy], 2)

    new_data = {
        "auto_updated": now,
        "auto_source":  "Bloomberg Terminal",
        "MKT": {
            "rate":  mkt_rate,
            "y10":   mkt_y10,
            "y2":    mkt_y2,
            "cot":   mkt_cot,
            "curve": mkt_curve,
            "gold":  [str(spot.get("XAUUSD", "")), ""],
            "brent": [str(spot.get("BRENT", "")), ""],
            "wti":   [str(spot.get("WTI", "")), ""],
            "dxy":   str(spot.get("DXY", "")),
        },
        "PX":    px,
        "SPOT":  {k: str(v) for k, v in spot.items()},
        "CAL":   calendar,
        "CB_NEXT": NEXT_MEETING,
    }

    # Preserve hand-edited keys
    preserve = ["BRIEF","PAIR","DEF","GEO","HOUSE","SCEN","HIST",
                "LO","OUT","outSum","L","CBX","ASSETS","bbSweep",
                "datav","researched","riskWhy","mom","momWhy",
                "cotNote","COTH","RETAIL"]
    for key in preserve:
        if key in existing:
            new_data[key] = existing[key]

    return new_data

# ─────────────────────────────────────────────────────────────────────────────
# Git push (optional — set AUTO_GIT=1 env var to enable)
# ─────────────────────────────────────────────────────────────────────────────

def git_push(repo_dir):
    import subprocess
    cmds = [
        ["git", "-C", repo_dir, "add", "data/desk_data.json", "data/desk_data.js"],
        ["git", "-C", repo_dir, "commit", "-m",
         f"chore: auto-update {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"],
        ["git", "-C", repo_dir, "push"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in r.stdout:
            print(f"  git warning: {r.stderr.strip()}", file=sys.stderr)
        else:
            print(f"  {' '.join(cmd[2:])}: ok")

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"FX Bias Desk — Bloomberg Fetch  {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    repo_dir = Path(__file__).parent.parent
    out_dir  = repo_dir / "data"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "desk_data.json"

    # Load existing data to preserve hand-edited fields
    existing = {}
    if out_file.exists():
        try:
            existing = json.loads(out_file.read_text())
        except:
            pass

    session = open_session()
    try:
        y10, y2  = fetch_yields(session)
        rates    = fetch_rates(session)
        spot     = fetch_spot(session)
        px       = fetch_history(session)
        cot      = fetch_cot(session)
        calendar = fetch_calendar(session)
    finally:
        session.stop()

    new_data = build_output(y10, y2, rates, spot, px, cot, calendar, existing)

    out_file.write_text(json.dumps(new_data, indent=2, ensure_ascii=False))
    print(f"\n✓  {out_file}  ({out_file.stat().st_size // 1024} KB)")

    js_file = out_dir / "desk_data.js"
    js_file.write_text(
        f"/* Bloomberg auto-update {datetime.now(timezone.utc).isoformat()} */\n"
        f"window.DESK_AUTO={json.dumps(new_data, separators=(',',':'))};")
    print(f"✓  {js_file}")

    if os.environ.get("AUTO_GIT") == "1":
        print("\nPushing to GitHub...")
        git_push(str(repo_dir))
        print("✓  GitHub Pages updated")
    else:
        print("\nTo push: set AUTO_GIT=1 or run: git add data && git commit -m 'update' && git push")

if __name__ == "__main__":
    main()
