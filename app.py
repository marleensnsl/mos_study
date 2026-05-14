"""
MOS Evaluation Study — Speech Synthesis
Master Project: Dialogue Speech Generation
"""

import streamlit as st
import os
import csv
import random
import hashlib
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURATION — Edit this section to update stimuli
# ─────────────────────────────────────────────

# Audio file paths — place your files accordingly
# Structure: audio/en/model_1/clip.wav, audio/en/model_2/clip.wav, ...
# Ground truth for EN: audio/en/ground_truth/clip.wav

# English stimuli: dialogues 2 and 20, each with one ground truth (AnnoMI)
# and eight model variants (cosyvoice, fishaudio, qwen3-tts, vits, and
# four speecht5 finetunes).
_EN_MODELS = [
    ("AnnoMI",            "AnnoMI (ground truth)"),
    ("cosyvoice",         "CosyVoice"),
    ("fishaudio",         "FishAudio"),
    ("qwen3-tts",         "Qwen3-TTS"),
    ("vits",              "VITS"),
    ("speecht5_base",     "SpeechT5 (base)"),
    ("speecht5_cosyvoice", "SpeechT5 (CosyVoice ft)"),
    ("speecht5_fishaudio", "SpeechT5 (FishAudio ft)"),
    ("speecht5_qwen3-tts", "SpeechT5 (Qwen3-TTS ft)"),
]

# German stimuli: dialogues 2 and 20. No AnnoMI ground truth (AnnoMI is
# English-only) and no VITS (English-only baseline). Only one SpeechT5
# finetune is available for German (fishaudio).
_DE_MODELS = [
    ("XTTS-v2",            "XTTS v2"),
    ("cosyvoice",          "CosyVoice"),
    ("fishaudio",          "FishAudio"),
    ("qwen3-tts",          "Qwen3-TTS"),
    ("speecht5_base",      "SpeechT5 (base)"),
    ("speecht5_fishaudio", "SpeechT5 (FishAudio ft)"),
]

EN_STIMULI = [
    {
        "id": f"en_d{dlg:02d}_{model_key.replace('-', '_')}",
        "label": f"EN-D{dlg:02d}-{model_label}",
        "path": f"dialogue_excerpts/english/dialogue_{dlg}/{dlg:02d}_{model_key}.wav",
    }
    for dlg in (2, 20)
    for model_key, model_label in _EN_MODELS
]

DE_STIMULI = [
    {
        "id": f"de_d{dlg:02d}_{model_key.replace('-', '_')}",
        "label": f"DE-D{dlg:02d}-{model_label}",
        "path": f"dialogue_excerpts/german/dialogue_{dlg:02d}/{dlg:02d}_{model_key}.wav",
    }
    for dlg in (2, 20)
    for model_key, model_label in _DE_MODELS
]

# Practice audio (should NOT be from main stimuli)
PRACTICE_STIMULI = [
    {
        "id": "practice_1",
        "label": "Practice 1",
        "path": "dialogue_excerpts/practice_trial/control874_fishaudio.wav",
    },
]

# Output directory for local-CSV fallback (used if Google Sheets is not configured
# or if a Sheets write fails). On Streamlit Cloud this is ephemeral.
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Google Sheets configuration. The spreadsheet ID and a service-account JSON
# blob are read from st.secrets when deployed; locally the app falls back to CSV.
GSHEET_RATINGS_WORKSHEET = "ratings"
GSHEET_COMMENTS_WORKSHEET = "comments"

RATING_COLUMNS = [
    "timestamp", "participant_id", "block", "stimulus_id", "stimulus_label",
    "position_in_block",
    "rating_naturalness", "rating_intelligibility",
    "rating_emotional_appropriateness", "rating_human_or_ai",
    "demo_age", "demo_gender", "demo_english_level", "demo_german_level",
    "demo_therapy_experience_receiving", "demo_therapy_experience_giving",
]

COMMENT_COLUMNS = ["timestamp", "participant_id", "comment"]

# Likert scale labels
LIKERT_OPTIONS = {
    1: "1 — Very poor",
    2: "2 — Poor",
    3: "3 — Fair",
    4: "4 — Good",
    5: "5 — Excellent",
}

DIMENSIONS = [
    {
        "key": "naturalness",
        "label": "Naturalness",
        "question": "How natural does the speech sound overall?",
        "anchors": ("Very unnatural", "Very natural"),
        "score_labels": {
            1: "Extremely synthetic, e.g.: robotic and monotonic",
            2: "",
            3: "Neutral",
            4: "",
            5: "Extremely natural, e.g.: indistinguishable from a human recording",
        },
    },
    {
        "key": "intelligibility",
        "label": "Intelligibility",
        "question": "How easy was it to understand what was being said?",
        "anchors": ("Very hard to understand", "Perfectly clear"),
        "score_labels": {
            1: "Very hard to understand, e.g.: most/all of the words cannot be understood",
            2: "",
            3: "Neutral",
            4: "",
            5: "Very easy to understand, e.g. most/all words are perfectly clear",
        },
    },

    {
        "key": "emotional_appropriateness",
        "label": "Emotional Appropriateness",
        "question": "How appropriate are the emotions conveyed in the speech for the dialogue context? (e.g. a client talking about something bad that happened should not sound happy)",
        "anchors": ("Completely inappropriate", "Perfectly appropriate"),
        "score_labels": {
            1: "Inappropriate, e.g.: most/all emotions of the speakers do not match with the context of the dialogue",
            2: "",
            3: "Neutral",
            4: "",
            5: "Appropriate, e.g.: most/all emotions of the speakers match with the context of the dialogue",
        },
    },
    {
        "key": "human_or_ai",
        "label": "Human or AI",
        "question": "Does this speech sound like it was produced by a human or generated by AI?",
        "type": "categorical",
        "options": ["Human", "Unsure", "AI"],
    },
]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_results_path(participant_id: str) -> str:
    safe_id = "".join(c for c in participant_id if c.isalnum() or c in "_-")
    return os.path.join(RESULTS_DIR, f"participant_{safe_id}.csv")


@st.cache_resource(show_spinner=False)
def _get_gspread_client():
    """Return an authorised gspread client, or None if not configured."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        return None
    if "gcp_service_account" not in st.secrets:
        return None
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _get_worksheet(name: str, headers_tuple: tuple):
    """Return a worksheet handle, creating it (with headers) if needed."""
    client = _get_gspread_client()
    if client is None:
        return None
    sheet_id = st.secrets.get("gsheet_id")
    if not sheet_id:
        return None
    spreadsheet = client.open_by_key(sheet_id)
    try:
        ws = spreadsheet.worksheet(name)
    except Exception:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers_tuple))
    if not ws.row_values(1):
        ws.append_row(list(headers_tuple))
    return ws


def _append_to_sheet(sheet_name: str, headers: list, row: list) -> bool:
    """Append a row to the given worksheet. Returns True on success."""
    try:
        ws = _get_worksheet(sheet_name, tuple(headers))
        if ws is None:
            return False
        ws.append_row(row, value_input_option="RAW")
        return True
    except Exception as e:
        try:
            st.toast(
                f"Cloud save failed, using local backup ({type(e).__name__}).",
                icon="⚠️",
            )
        except Exception:
            pass
        return False


def _append_to_csv(path: str, headers: list, row: list):
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)


def _fetch_participant_history(participant_id: str) -> list:
    """Return all existing rating rows for this participant (Sheets, with CSV fallback)."""
    try:
        ws = _get_worksheet(GSHEET_RATINGS_WORKSHEET, tuple(RATING_COLUMNS))
        if ws is not None:
            records = ws.get_all_records()
            return [
                r for r in records
                if str(r.get("participant_id", "")).strip().lower() == participant_id
            ]
    except Exception:
        pass
    path = get_results_path(participant_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _compute_resume_state(participant_id: str, history: list):
    """Compute resume info from previous rows. Returns None if no history."""
    if not history:
        return None
    history_sorted = sorted(history, key=lambda r: str(r.get("timestamp", "")))
    last = history_sorted[-1]
    demographics = {
        "age": last.get("demo_age", ""),
        "gender": last.get("demo_gender", ""),
        "english_level": last.get("demo_english_level", ""),
        "german_level": last.get("demo_german_level", ""),
        "therapy_experience_receiving": last.get("demo_therapy_experience_receiving", ""),
        "therapy_experience_giving": last.get("demo_therapy_experience_giving", ""),
    }
    completed_ids = {r.get("stimulus_id") for r in history if r.get("stimulus_id")}

    h = int(hashlib.md5(participant_id.encode()).hexdigest(), 16)
    language_order = ["en", "de"] if h % 2 == 0 else ["de", "en"]
    en_order = deterministic_shuffle(list(range(len(EN_STIMULI))), seed=participant_id + "_en")
    de_order = deterministic_shuffle(list(range(len(DE_STIMULI))), seed=participant_id + "_de")
    total = len(EN_STIMULI) + len(DE_STIMULI)

    completed_blocks = []
    for block in language_order:
        order = en_order if block == "en" else de_order
        stimuli = EN_STIMULI if block == "en" else DE_STIMULI
        for idx, stim_idx in enumerate(order):
            if stimuli[stim_idx]["id"] not in completed_ids:
                return {
                    "all_done": False,
                    "demographics": demographics,
                    "language_order": language_order,
                    "en_order": en_order,
                    "de_order": de_order,
                    "block": block,
                    "stimulus_index": idx,
                    "completed_blocks": completed_blocks[:],
                    "completed_count": len(completed_ids),
                    "total_count": total,
                }
        completed_blocks.append(block)
    return {
        "all_done": True,
        "demographics": demographics,
        "completed_count": len(completed_ids),
        "total_count": total,
    }


def save_rating(participant_id: str, block: str, stimulus_id: str,
                stimulus_label: str, position: int, ratings: dict,
                demographics: dict):
    """Persist a single stimulus rating (Google Sheets first, CSV as fallback)."""
    row_dict = {
        "timestamp": datetime.now().isoformat(),
        "participant_id": participant_id,
        "block": block,
        "stimulus_id": stimulus_id,
        "stimulus_label": stimulus_label,
        "position_in_block": position,
        **{f"rating_{k}": v for k, v in ratings.items()},
        **{f"demo_{k}": v for k, v in demographics.items()},
    }
    row = [row_dict.get(col, "") for col in RATING_COLUMNS]

    if not _append_to_sheet(GSHEET_RATINGS_WORKSHEET, RATING_COLUMNS, row):
        _append_to_csv(get_results_path(participant_id), RATING_COLUMNS, row)


def save_comment(participant_id: str, comment: str):
    row_dict = {
        "timestamp": datetime.now().isoformat(),
        "participant_id": participant_id,
        "comment": comment,
    }
    row = [row_dict[col] for col in COMMENT_COLUMNS]
    if not _append_to_sheet(GSHEET_COMMENTS_WORKSHEET, COMMENT_COLUMNS, row):
        _append_to_csv(
            os.path.join(RESULTS_DIR, "comments.csv"),
            COMMENT_COLUMNS, row,
        )


def deterministic_shuffle(items: list, seed: str) -> list:
    """Shuffle a list deterministically based on a seed string."""
    items = items.copy()
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    rng = random.Random(h)
    rng.shuffle(items)
    return items


def init_session():
    """Initialise all session state keys that don't exist yet."""
    defaults = {
        "page": "welcome",
        "participant_id": "",
        "demographics": {},
        "language_order": ["en", "de"],
        "en_order": list(range(len(EN_STIMULI))),
        "de_order": list(range(len(DE_STIMULI))),
        "practice_index": 0,
        "block": "en",           # current block
        "stimulus_index": 0,     # position within current block
        "listened": False,
        "current_ratings": {},
        "completed_blocks": [],
        "comment_saved": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def go_to(page: str):
    st.session_state.page = page
    st.session_state.listened = False
    st.session_state.current_ratings = {}
    st.rerun()


def progress_bar(current: int, total: int, label: str = ""):
    fraction = current / total if total > 0 else 0
    st.progress(fraction, text=f"{label}  {current} / {total}")


# ─────────────────────────────────────────────
# PAGE FUNCTIONS
# ─────────────────────────────────────────────

def page_welcome():
    st.title("Evaluating properties of AI-generated therapeutic speech")

    st.markdown("""
    ### Welcome and thank you for participating!

    This study is part of a Master Thesis project at the **Technische Universität Darmstadt**.

    - **Master Thesis student:** Marleen Sinsel
    - **Supervisors:** Dr. Simone Balloccu, Doan Nam Long Vu
    - **Contact:** marleen.sinsel@stud.tu-darmstadt.de

    You will be asked to listen to a series of audio excerpts of therapeutic conversations
    and rate them on several perceptual dimensions. These audio clips may come from real human speakers or AI speech synthesis systems.

    **What to expect:**
    - The study consists of two parts (English and German) and takes approximately **35-40 minutes** in total.

    **Important Prerequisites:**
    - You need a stable internet connection
    - Please use **headphones** for the best listening experience
    - Please conduct the study on a laptop or desktop computer in a quiet environment
    """)

    st.warning(
        "**Language requirement:** You must understand spoken English **and** German well "
        "(at least **B2 / upper-intermediate** level in both). If this does not apply to you, please do not participate."
    )

    st.divider()

    st.markdown("""
    ### Information Sheet & Privacy Statement
    We kindly ask you to read the following explanations carefully and to sign the present declaration of consent before you take part in the study.
                
    **Subject of the study**  
    This study investigates how humans perceive speech from AI speech synthesis systems and real human speakers in the context of therapeutic conversations, by rating audio clips on various perceptual dimensions.

    **Process of the study**  
    Participants will listen to a series of audio clips of therapeutic conversations and rate each 
    clip on four perceptual dimensions: Naturalness, Intelligibility, Emotional Appropriateness, 
    and a Human-or-AI judgement. Before the main study, participants complete a short practice 
    trial to familiarise themselves with the task. The study consists of two parts (one with English 
    clips, one with German clips). Participants are asked to use 
    headphones in a quiet environment on a laptop or desktop computer.
                
    **Duration and compensation for participation**  
    Participation in the study will require approximately 35-40 minutes. Participants will not receive 
    any kind of gratification.

    **Possible benefit of the study**  
    This study contributes to research on the perceptual quality of AI-generated speech in mental health. Results may inform the development of more natural 
    speech synthesis systems for therapeutic applications or training resources for therapeutic learners.

    **Experiences and risks associated with participation**  
    The participants of the study do not face any risks which are greater than risks they face in 
    general life.

    ---

    **Privacy Statement**

    Data processing in the context of this study is performed according to the privacy regulations 
    of the General Data Protection Regulation (GDPR) and the Privacy and Freedom of Information law 
    of the State of Hessen (HDSIG). All data will only be used for the purposes described in this 
    Information Sheet.

    In the context of this study, the following information will be collected:  
    Perceptual ratings of audio clips.
                
    Personal data collected are:  
    Age, sex, and whether the participant has experience with therapeutic conversations.

    **Confidentiality**  
    All data collected in course of the study are naturally confidential and will only be used in anonymized form. Demographic data like age or sex do not allow deducing unambiguous information about your person. You will be asked at no point of the study to disclose your name or other unambiguous information about yourself.

    **Data storage**  
    Collected data will be stored locally on the Master Thesis student's password-protected laptop. Data storage takes place in a form which does not allow 
    conclusions about your person, meaning that all data will be anonymized. 

    **Voluntariness & Rights of the participants**  
    Your participation in this study is voluntary. You can withdraw from participation at any point 
    in time without facing any disadvantages. If you withdraw from participation, no data connected 
    to your person will be stored and already collected data will be deleted.  
    You have the right to request which data about your person have been stored and — if necessary — 
    demand that they are either corrected or deleted. You also have the right to restrict processing, 
    the right to object to processing and the right to data portability in a commonly used, structured 
    and machine-readable form.  
    In case of dissent you have the right to lodge a complaint with the Data Protection Officer of 
    Hessen: Email: Poststelle@datenschutz.hessen.de

    ---

    **Declaration of Consent**  
    I have read the explanations regarding the study and I hereby agree to participate.  
    I agree that any data collected in the course of the study will be analyzed for scientific 
    purposes and stored in anonymized form. I am aware that my participation is voluntary and that 
    I can withdraw at any time and without giving reasons.
    
    If you have any questions, suggestions or complaints, you are welcome to contact Marleen Sinsel: marleen.sinsel@stud.tu-darmstadt.de
    """)

    consent = st.checkbox(
        "I confirm that I have read and understood the above information and agree to participate in this study."
    )
    language_consent = st.checkbox(
        "I confirm that I understand spoken **English and German** at B2 level (upper-intermediate) or higher."
    )

    st.divider()
    st.markdown("#### Please enter a participant code.")
    st.markdown("*Use a code you will remember (e.g. last two letters of mother's name + last two numbers of your telephone number. eg: KE00")

    pid = st.text_input("Participant code", max_chars=20,
                        placeholder="e.g. KE00",
                        value=st.session_state.participant_id)

    if st.button("Continue →", disabled=not (consent and language_consent) or len(pid.strip()) < 3):
        normalized = pid.strip().lower()
        st.session_state.participant_id = normalized

        # If this participant has prior ratings, resume where they left off.
        history = _fetch_participant_history(normalized)
        resume = _compute_resume_state(normalized, history)

        if resume and resume.get("all_done"):
            st.session_state.demographics = resume["demographics"]
            st.session_state._resume_banner = (
                "This participant code has already completed the study. "
                "Thank you — there is nothing more to rate."
            )
            go_to("thank_you")

        if resume:
            st.session_state.demographics = resume["demographics"]
            st.session_state.language_order = resume["language_order"]
            st.session_state.en_order = resume["en_order"]
            st.session_state.de_order = resume["de_order"]
            st.session_state.block = resume["block"]
            st.session_state.stimulus_index = resume["stimulus_index"]
            st.session_state.completed_blocks = resume["completed_blocks"]
            st.session_state._resume_banner = (
                f"Welcome back — resuming where you left off "
                f"({resume['completed_count']}/{resume['total_count']} clips already rated)."
            )
            go_to("rating")

        # Fresh participant.
        h = int(hashlib.md5(normalized.encode()).hexdigest(), 16)
        if h % 2 == 0:
            st.session_state.language_order = ["en", "de"]
        else:
            st.session_state.language_order = ["de", "en"]

        st.session_state.en_order = deterministic_shuffle(
            list(range(len(EN_STIMULI))), seed=normalized + "_en")
        st.session_state.de_order = deterministic_shuffle(
            list(range(len(DE_STIMULI))), seed=normalized + "_de")

        go_to("demographics")


def page_demographics():
    st.title("Background Information")
    st.markdown("Please answer the following questions about yourself.")
    st.divider()

    with st.form("demographics_form"):
        age = st.number_input("Age", min_value=18, max_value=99, step=1, value=None)

        gender = st.selectbox(
            "Gender",
            options=["", "Female", "Male", "Prefer not to say"],
        )

        st.markdown("##### Experience with therapeutic conversations")
        therapy_exp_receiving = st.radio(
            "How much experience do you have with **receiving** therapy (as a patient/client)?",
            options=[
                "None",
                "Some (one-time experience)",
                "Moderate (e.g. occasional therapy sessions)",
                "Extensive (e.g. ongoing or long-term therapy)",
            ],
            key="therapy_receiving",
        )
        therapy_exp_giving = st.radio(
            "How much experience do you have with **giving** therapy (as a therapist or student)?",
            options=[
                "None",
                "Some (e.g. a single practicum or role-play exercise)",
                "Moderate (e.g. coursework)",
                "Extensive (e.g. professional training or practicing therapist)",
            ],
            key="therapy_giving",
        )

        submitted = st.form_submit_button("Continue →")

    if submitted:
        if age is None or gender == "":
            st.error("Please fill in all fields.")
        else:
            st.session_state.demographics = {
                "age": age,
                "gender": gender,
                "therapy_experience_receiving": therapy_exp_receiving,
                "therapy_experience_giving": therapy_exp_giving,
            }
            go_to("instructions")


def page_instructions():
    st.title("Instructions")

    st.markdown("""
    You will listen to and rate parts of therapy conversations.
                
    **How each trial works:**
    1. Listen to the full clip.
    2. Once you have listened, tick the checkbox to confirm.
    3. Rate the speech of both speakers (patient and therapist) on all four dimensions.
    4. Press **Submit Rating** to move to the next clip.

    ---
                
    | Dimension | What you will rate |
    |---|---|
    | **Naturalness** | Does the speech sound like a real human talking, with natural variation in pitch, rhythm, and emphasis? |
    | **Intelligibility** | Can you clearly understand every word? |
    | **Emotional Appropriateness** | Do the emotions in the voice fit what is being said in the conversation? |
    | **Human or AI** | Does the speech sound like a human or AI? Choose: *Human*, *Unsure*, or *AI*. |


    """)

    st.warning(
        "Please evaluate the way the dialogue is spoken, not sentence structure, grammar or word choice. "
        "Focus on vocal characteristics such as naturalness, clarity, and fit to the situation. Please rate the speech of both speakers (patient and therapist)."
        
    )
    st.warning(
        "Also: please listen to the **complete audio** before rating. You may replay it as many times as you like."
    )

    st.markdown("""
    ---

    **Structure of the study:**
    - First, you will complete a **practice trial** to get familiar with the task.
    - Then the main study begins in two blocks (English and German).
    - A short break screen will appear between blocks.
    """)

    if st.button("Start practice trials →"):
        st.session_state.practice_index = 0
        go_to("practice")


def page_practice():
    idx = st.session_state.practice_index
    total = len(PRACTICE_STIMULI)
    stimulus = PRACTICE_STIMULI[idx]

    st.title(f"Practice Trial {idx + 1}/{total}")
    st.info("This is a practice trial. Your ratings here will **not** be recorded.")
    progress_bar(idx, total, "Practice")
    st.divider()
    st.warning(
        "Please evaluate the way the dialogue is spoken, not sentence structure, grammar or word choice. "
        "Focus on vocal characteristics such as naturalness, clarity, and fit to the situation.Please rate the speech of both speakers (patient and therapist)."
        
    )
    render_stimulus(stimulus, is_practice=True)

    if st.session_state.listened and len(st.session_state.current_ratings) == len(DIMENSIONS):
        if st.button("Next →" if idx < total - 1 else "Start main study →"):
            if idx < total - 1:
                st.session_state.practice_index += 1
                st.session_state.listened = False
                st.session_state.current_ratings = {}
                st.rerun()
            else:
                # Set first block
                st.session_state.block = st.session_state.language_order[0]
                st.session_state.stimulus_index = 0
                go_to("block_intro")


def page_block_intro():
    block = st.session_state.block
    lang_name = "English" if block == "en" else "German"
    total = len(EN_STIMULI) if block == "en" else len(DE_STIMULI)

    st.title(f"{lang_name} Block")
    st.markdown(f"""
    You are about to start the **{lang_name} block**.

    - This block contains **{total} audio clips**.
    - Rate each clip on the same four dimensions as in the practice trials.
    - Please rate the speech of both speakers as a whole.
    """)

    if st.button(f"Begin {lang_name} block →"):
        go_to("rating")


def page_rating():
    block = st.session_state.block
    order = st.session_state.en_order if block == "en" else st.session_state.de_order
    stimuli = EN_STIMULI if block == "en" else DE_STIMULI

    idx = st.session_state.stimulus_index
    total = len(order)
    stimulus = stimuli[order[idx]]

    lang_name = "English" if block == "en" else "German"

    st.title(f"{lang_name} Block — Clip {idx + 1}/{total}")
    progress_bar(idx, total, f"{lang_name} block")
    st.divider()
    st.warning(
        "Please evaluate the way the dialogue is spoken, not sentence structure, grammar or word choice. "
        "Focus on vocal characteristics such as naturalness, clarity, and fit to the situation. "
        "Please rate the speech of both speakers (patient and therapist)."
    )
    render_stimulus(stimulus, is_practice=False)

    all_rated = len(st.session_state.current_ratings) == len(DIMENSIONS)

    if st.session_state.listened and all_rated:
        if st.button("Submit Rating →", type="primary"):
            # Save to CSV
            save_rating(
                participant_id=st.session_state.participant_id,
                block=block,
                stimulus_id=stimulus["id"],
                stimulus_label=stimulus["label"],
                position=idx,
                ratings=st.session_state.current_ratings,
                demographics=st.session_state.demographics,
            )

            # Advance
            if idx < total - 1:
                st.session_state.stimulus_index += 1
                st.session_state.listened = False
                st.session_state.current_ratings = {}
                st.rerun()
            else:
                # Block finished
                st.session_state.completed_blocks.append(block)
                remaining = [b for b in st.session_state.language_order
                             if b not in st.session_state.completed_blocks]
                if remaining:
                    st.session_state.block = remaining[0]
                    st.session_state.stimulus_index = 0
                    go_to("break")
                else:
                    go_to("thank_you")


def page_break():
    next_block = st.session_state.block
    lang_name = "English" if next_block == "en" else "German"
    st.title("Short Break")
    st.markdown(f"""
    Take a moment to rest before continuing with the **{lang_name} block**.

    When you feel ready, press the button below.
    """)

    if st.button(f"Continue to {lang_name} block →"):
        go_to("block_intro")


def page_thank_you():
    pid = st.session_state.participant_id
    st.title("Study concluded")
    st.success("Thank you for your participation!")
    st.markdown(f"""
    Your responses have been saved successfully under participant code **{pid}**.
    """)

    st.divider()
    st.markdown("#### Feedback(optional)")
    comment = st.text_area(
        "Feel free to share any feedback you have about this experiment",
        key="comment_input",
        disabled=st.session_state.comment_saved,
    )
    if not st.session_state.comment_saved:
        if st.button("Submit comment"):
            save_comment(pid, comment)
            st.session_state.comment_saved = True
            st.rerun()
    else:
        st.success("Comment saved!")

    st.markdown(" You may now close the window.")


# ─────────────────────────────────────────────
# SHARED STIMULUS RENDERING
# ─────────────────────────────────────────────

def _set_rating(dim_key: str, val):
    st.session_state.current_ratings[dim_key] = val


def render_stimulus(stimulus: dict, is_practice: bool):
    """Render the audio player and Likert rating form for one stimulus."""
    audio_path = stimulus["path"]
    st.markdown("#### Listen to the audio clip")
    st.caption("You may replay as many times as needed.")

    if os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes, format="audio/wav")
    else:
        st.warning(
            f"Audio file not found: `{audio_path}`\n\n"
            "*(Placeholder)*"
        )

    listened = st.checkbox(
        "✅ I have listened to the complete audio clip",
        value=st.session_state.listened,
        key=f"listened_{stimulus['id']}_{is_practice}",
    )
    st.session_state.listened = listened

    if not listened:
        st.info("Please listen to the full clip and tick the checkbox above before rating.")
        return

    st.divider()
    st.markdown("#### Rate the clip on the following dimensions")
    st.caption("1 = lowest, 5 = highest")

    for dim in DIMENSIONS:
        st.markdown(f"**{dim['label']}** — *{dim['question']}*")
        key = f"rating_{stimulus['id']}_{dim['key']}_{is_practice}"

        if dim.get("type") == "categorical":
            rating = st.radio(
                label=dim["label"],
                options=dim["options"],
                horizontal=True,
                index=None,
                label_visibility="collapsed",
                key=key,
            )
            if rating is not None:
                st.session_state.current_ratings[dim["key"]] = rating
        else:
            anchor_cols = st.columns(5)
            with anchor_cols[0]:
                st.caption(f"⬅ {dim['anchors'][0]}")
            with anchor_cols[4]:
                st.markdown(
                    f"<p style='text-align:right; font-size:0.8rem; color:grey; margin:0;'>{dim['anchors'][1]} ➡</p>",
                    unsafe_allow_html=True,
                )

            current_val = st.session_state.current_ratings.get(dim["key"])
            btn_cols = st.columns(5)
            for i, val in enumerate([1, 2, 3, 4, 5]):
                with btn_cols[i]:
                    st.button(
                        str(val),
                        key=f"{key}_{val}",
                        type="primary" if current_val == val else "secondary",
                        use_container_width=True,
                        on_click=_set_rating,
                        args=(dim["key"], val),
                    )

            score_labels = dim.get("score_labels")
            if score_labels:
                lbl_cols = st.columns(5)
                for i, val in enumerate([1, 2, 3, 4, 5]):
                    with lbl_cols[i]:
                        st.caption(score_labels[val])

        st.markdown("")  # spacing

    rated_count = len(st.session_state.current_ratings)
    if rated_count < len(DIMENSIONS):
        st.caption(f"*Please rate all dimensions ({rated_count}/{len(DIMENSIONS)} done)*")


# ─────────────────────────────────────────────
# MAIN ROUTER
# ─────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Speech Perception Study",
        page_icon="🎧",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Hide sidebar entirely
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none; }
        .block-container { max-width: 1400px; padding-top: 2rem; margin: 0 auto; }
        </style>
    """, unsafe_allow_html=True)

    init_session()

    # One-shot resume banner (set by page_welcome when prior data was found).
    if "_resume_banner" in st.session_state:
        st.info(st.session_state["_resume_banner"])
        del st.session_state["_resume_banner"]

    # Scroll back to top whenever the user navigates to a new page or new stimulus.
    nav_state = (
        st.session_state.page,
        st.session_state.stimulus_index,
        st.session_state.practice_index,
    )
    if st.session_state.get("_last_nav_state") != nav_state:
        st.session_state._last_nav_state = nav_state
        st.components.v1.html(
            """
            <script>
              const doc = window.parent.document;
              const win = window.parent;

              function scrollAllToTop() {
                const candidates = [
                  doc.querySelector('section.main'),
                  doc.querySelector('.main'),
                  doc.querySelector('[data-testid="stAppViewContainer"]'),
                  doc.querySelector('[data-testid="stMain"]'),
                  doc.querySelector('section[data-testid="stMain"]'),
                  doc.scrollingElement,
                  doc.documentElement,
                  doc.body,
                ];
                for (const t of candidates) {
                  if (!t) continue;
                  try { t.scrollTop = 0; } catch (e) {}
                  try { if (t.scrollTo) t.scrollTo({top: 0, behavior: 'instant'}); } catch (e) {}
                }
                try { win.scrollTo({top: 0, behavior: 'instant'}); } catch (e) {}
              }

              // Immediate + paced retries for the first second.
              scrollAllToTop();
              [0, 50, 150, 350, 700, 1200].forEach(d => setTimeout(scrollAllToTop, d));

              // For up to 2.5s, scroll back to top on every DOM mutation
              // (covers Streamlit's late layout passes after rerun).
              try {
                const observer = new MutationObserver(() => scrollAllToTop());
                observer.observe(doc.body, {childList: true, subtree: true});
                setTimeout(() => observer.disconnect(), 2500);
              } catch (e) {}
            </script>
            """,
            height=0,
            width=0,
        )

    page = st.session_state.page
    if page == "welcome":          page_welcome()
    elif page == "demographics":   page_demographics()
    elif page == "instructions":   page_instructions()
    elif page == "practice":       page_practice()
    elif page == "block_intro":    page_block_intro()
    elif page == "rating":         page_rating()
    elif page == "break":          page_break()
    elif page == "thank_you":      page_thank_you()
    else:
        st.error(f"Unknown page: {page}")


if __name__ == "__main__":
    main()