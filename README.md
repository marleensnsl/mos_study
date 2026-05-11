# MOS Evaluation Study — Setup Guide

## Folder Structure

```
mos_study/
├── app.py                  ← Main Streamlit app
├── requirements.txt
├── results/                ← Auto-created; one CSV per participant
└── audio/
    ├── practice/
    │   ├── practice_1.wav  ← Practice clip 1 (NOT from main study)
    │   └── practice_2.wav  ← Practice clip 2
    ├── en/
    │   ├── ground_truth/
    │   │   └── clip.wav    ← English ground truth audio
    │   ├── model_1/
    │   │   └── clip.wav
    │   ├── model_2/
    │   │   └── clip.wav
    │   ├── model_3/
    │   │   └── clip.wav
    │   ├── model_4/
    │   │   └── clip.wav
    │   ├── model_5/
    │   │   └── clip.wav
    │   ├── model_6/
    │   │   └── clip.wav
    │   └── model_7/
    │       └── clip.wav
    └── de/
        ├── model_1/
        │   └── clip.wav
        ├── model_2/
        │   └── clip.wav
        ├── model_3/
        │   └── clip.wav
        ├── model_4/
        │   └── clip.wav
        ├── model_5/
        │   └── clip.wav
        ├── model_6/
        │   └── clip.wav
        └── model_7/
            └── clip.wav
```

## Quick Start (Local)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment on Streamlit Community Cloud (free, shareable link)

1. Push this folder to a **GitHub repository** (public or private).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **New app** → select your repo, branch, and `app.py`.
4. Click **Deploy**. You get a link like `https://yourname-study.streamlit.app`.

> ⚠️ On Streamlit Community Cloud, the `results/` CSV files are **not persistent**
> between restarts. The app writes ratings to a Google Sheet instead. See setup below.

## Persistent Storage — Google Sheets

The app writes every rating row directly to a Google Sheet using a service account.
If the Sheets call fails or no credentials are configured (e.g. local dev), it falls
back to writing a CSV in `results/`.

### One-time setup

1. **Create a Google Cloud project** at https://console.cloud.google.com → *New Project*.
2. **Enable the APIs** under *APIs & Services → Library*:
   - Google Sheets API
   - Google Drive API
3. **Create a service account** under *IAM & Admin → Service Accounts → Create*:
   - Name it e.g. `study-writer`
   - No roles needed at the project level — sharing the sheet is enough
   - Open the new account → *Keys → Add key → JSON*. A JSON file downloads.
4. **Create the Google Sheet** at https://sheets.google.com (e.g. `mos_study_results`).
   - Note the spreadsheet ID from the URL: `docs.google.com/spreadsheets/d/<ID>/edit`
   - Click *Share* → paste the service account's `client_email` (from the JSON,
     looks like `study-writer@your-project.iam.gserviceaccount.com`) → give *Editor* access.
5. **Add the credentials to Streamlit secrets:**
   - **Locally:** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
     and fill in the values from the JSON file. **Do not commit this file** — it is
     already in `.gitignore`.
   - **On Streamlit Cloud:** go to your app → *Settings → Secrets* → paste the same
     TOML content into the editor. Save.

The two worksheets `ratings` and `comments` are auto-created on the first write,
including a header row.

### Verifying the setup

After deploying, complete one practice trial and one real rating. Open the Google
Sheet — a new row should appear in the `ratings` worksheet within a few seconds.
If you see a small "Cloud save failed, using local backup" toast in the app, the
service account doesn't have access to the sheet (most common cause: forgot to
share it with the `client_email`).

## Alternative: Local-only deployment

If you'd rather run the study on your own machine, skip the Sheets setup —
results are written to `results/participant_<id>.csv`. Expose with `ngrok` or
similar:
```bash
streamlit run app.py --server.port 8501
ngrok http 8501
```

## Editing Stimuli

All stimuli are defined at the top of `app.py` in the `EN_STIMULI` and `DE_STIMULI` lists.
Update the `"path"` fields to point to your actual audio files.
Model labels (`"label"`) are never shown to participants — they are only in the CSV.

## Results CSV Format

One CSV per participant, saved in `results/participant_<id>.csv`:

| Column | Description |
|---|---|
| timestamp | ISO datetime of submission |
| participant_id | Anonymised code entered by participant |
| block | `en` or `de` |
| stimulus_id | Internal ID (e.g. `en_m1`) |
| stimulus_label | Label (e.g. `EN-M1`) — not shown to participant |
| position_in_block | 0-indexed position in the randomised block |
| rating_naturalness | 1–5 |
| rating_intelligibility | 1–5 |
| rating_expressiveness | 1–5 |
| rating_emotional_appropriateness | 1–5 |
| demo_age | Self-reported age |
| demo_gender | Self-reported gender |
| demo_english_level | CEFR level |
| demo_german_level | CEFR level |
| demo_therapy_experience | Category |

## Randomisation Logic

- Stimulus order within each block: deterministically shuffled per participant using
  MD5 hash of participant ID. Reproducible — same ID always gives same order.
- Language block order: even hash → EN first; odd hash → DE first.
  Approximately half of participants will do each order.
