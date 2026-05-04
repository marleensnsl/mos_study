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
> between restarts. Use one of the options below for persistent storage.

## Persistent Storage Options

### Option A — Google Sheets (Recommended for simplicity)
Use `gspread` + `st.secrets` to write each row to a Google Sheet instead of CSV.
See: https://docs.streamlit.io/develop/tutorials/databases/public-gsheet

### Option B — Local deployment (TU network / own server)
Run locally on a machine that stays on, expose via `ngrok` or university server:
```bash
pip install streamlit
streamlit run app.py --server.port 8501
ngrok http 8501   # gives you a public URL
```

### Option C — Export CSV manually
Ask participants to download their own responses via the download button on the
thank-you page, then email the CSV to you.

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
