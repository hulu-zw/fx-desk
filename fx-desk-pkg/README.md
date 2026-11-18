# FX Bias Desk — Standalone (No Claude Required)

The desk runs on **GitHub Pages** (private repo, GitHub Pro).
Data is updated daily by a **Python + Bloomberg** script on your PC.
Zero Claude quota used after setup.

---

## Architecture

```
Bloomberg Terminal (your PC, open daily)
    └── Python script (Windows Task Scheduler, 07:00 daily)
        ├── Fetches: yields, rates, spot, history, COT, calendar
        ├── Computes: SMA/EMA 20/50/100/200, RSI, curve spreads
        └── Writes: data/desk_data.json  →  git push
                              ↓
                   GitHub Pages serves the desk
                              ↓
              https://YOUR_USERNAME.github.io/fx-desk
              (or custom domain via CNAME)
```

---

## One-time Setup

### Step 1 — Install blpapi (Bloomberg Python API)

Open Command Prompt and run:
```
pip install blpapi --index-url https://bcms.bloomberg.com/pip/simple
```
Bloomberg Terminal must be installed first. Test with:
```
python -c "import blpapi; print('OK')"
```

### Step 2 — Create the GitHub repo

1. Go to github.com → **New repository**
2. Name: `fx-desk`
3. Set to **Private** (GitHub Pro supports private Pages)
4. Initialize with a README

### Step 3 — Clone and add files

```bash
git clone https://github.com/YOUR_USERNAME/fx-desk.git
cd fx-desk
```

Copy these files into the repo:
```
fx-desk/
├── index.html              ← the desk HTML (renamed from fx-bias-desk.html)
├── data/
│   └── desk_data.json      ← created by the script on first run
├── scripts/
│   └── fetch_bloomberg.py  ← the fetcher
├── run_desk_update.bat     ← double-click or Task Scheduler
└── README.md
```

Commit and push:
```bash
git add .
git commit -m "init"
git push
```

### Step 4 — Enable GitHub Pages

1. GitHub repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / folder: `/ (root)`
4. Save → your desk is live at:
   `https://YOUR_USERNAME.github.io/fx-desk`

### Step 5 — Edit run_desk_update.bat

Change `REPO_DIR` to match where you cloned the repo:
```bat
set REPO_DIR=C:\Users\YourName\Documents\fx-desk
```

Test by double-clicking the .bat file with Bloomberg open.
You should see `✓ desk_data.json` and the GitHub push.

### Step 6 — Set up Task Scheduler

1. Open **Task Scheduler** (search in Start menu)
2. **Create Basic Task**
3. Name: `FX Desk Update`
4. Trigger: **Daily** at **07:00** (adjust to your morning routine)
5. Action: **Start a program**
6. Program: browse to `run_desk_update.bat`
7. Finish

That's it. Every morning at 07:00, Bloomberg is queried and GitHub is updated.

---

## Updating CB rates after a meeting

Open `scripts/fetch_bloomberg.py` and edit the `NEXT_MEETING` dict:
```python
NEXT_MEETING = {
    "USD": "27/01/2027",   # updated after Dec FOMC
    ...
}
```
Then run the script once or let it run on schedule.

---

## Cancel Claude scheduled tasks (do this after setup is confirmed working)

Log into claude.ai → Settings → Scheduled tasks → delete:
- Watchdog
- Daily price backfill
- London / Macro runs
- Any remaining triggers

Your Claude Pro quota returns to normal immediately.

---

## Cost summary

| Item | Cost |
|---|---|
| GitHub Pages (private) | Included in GitHub Pro |
| Bloomberg data | Included in your existing subscription |
| Python + Task Scheduler | Free (Windows built-in) |
| Claude Pro usage (ongoing) | **Zero** |

---

## Optional: Custom domain

Add a `CNAME` file to the repo root containing your domain:
```
desk.yourdomain.com
```
Then add a DNS CNAME record pointing to `YOUR_USERNAME.github.io`.
Takes ~10 minutes to propagate.
