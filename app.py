"""
ESG Analyzer - Corporate Report Processing System
=================================================
Module 1: PDF processing, text extraction and RULE-BASED ESG indicator detection.

* Libraries: Streamlit, PyMuPDF (fitz), Pandas (+ Python standard library only).
* No AI, no LLMs, no external APIs, no OCR: the 25 ESG indicators are found with
  keyword rules that are checked IN CONTEXT (sentence windows, required context
  words, evidence words, exclusion patterns).
* Terminology covers Indian BRSR (SEBI), GRI Standards and ESRS disclosures.

Run with:  streamlit run app.py
"""

import hashlib
import html
import re
from collections import Counter
from datetime import datetime

import fitz  # PyMuPDF
import pandas as pd
import streamlit as st

# =============================================================================
# 1. PAGE CONFIGURATION AND CONSTANTS
# =============================================================================
st.set_page_config(
    page_title="ESG Analyzer",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

NOT_AVAILABLE = "Not available"
NO_INDICATORS = "—"

CATEGORY_ORDER = ["Environmental", "Social", "Governance"]
CATEGORY_CLASS = {"Environmental": "env", "Social": "soc", "Governance": "gov"}

CONFIDENCE_LEVELS = ["Low", "Medium", "High"]
CONFIDENCE_RANK = {level: rank for rank, level in enumerate(CONFIDENCE_LEVELS)}
DEFAULT_CONFIDENCE = "Medium"

# =============================================================================
# 2. STYLING (forest green / emerald / off-white theme)
# =============================================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{
  --forest:#14452f; --forest-dark:#0d2f20; --emerald:#10b981; --emerald-dark:#059669;
  --mint:#d1fae5; --offwhite:#f6f4ee; --ink:#1c2b24; --muted:#6b7a72; --border:#e3e8e2;
}
.stApp{font-family:'Inter',-apple-system,'Segoe UI',Roboto,sans-serif;background:var(--offwhite);color:var(--ink);}
.block-container{padding-top:1.8rem;padding-bottom:3rem;max-width:1250px;}
#MainMenu, footer{visibility:hidden;}
header[data-testid="stHeader"]{background:transparent;}
.stApp label p{color:var(--ink);font-weight:600;}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--forest-dark) 0%,var(--forest) 100%);}
.sb-brand{display:flex;align-items:center;gap:.75rem;padding:.3rem 0 .6rem;}
.sb-logo{width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,#34d399,#059669);display:flex;align-items:center;justify-content:center;font-size:1.5rem;box-shadow:0 4px 12px rgba(0,0,0,.25);}
.sb-title{color:#ffffff;font-weight:800;font-size:1.3rem;line-height:1.1;}
.sb-sub{color:#a7d7bf;font-size:.72rem;margin-top:2px;}
.sb-section{color:#7fc9a3;font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;margin:1.4rem 0 .5rem;font-weight:700;}
.sb-card{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:.85rem .95rem;color:#e8f5ee;font-size:.85rem;line-height:1.5;}
.sb-card b{color:#ffffff;}
.sb-step{display:flex;gap:.6rem;align-items:flex-start;color:#e8f5ee;font-size:.85rem;margin-bottom:.55rem;}
.sb-num{min-width:22px;height:22px;border-radius:50%;background:#10b981;color:#06281a;font-weight:700;font-size:.72rem;display:flex;align-items:center;justify-content:center;}
.pill{display:inline-block;padding:.12rem .6rem;border-radius:999px;font-size:.72rem;font-weight:700;}
.pill-ok{background:#d1fae5;color:#065f46;} .pill-warn{background:#fef3c7;color:#92400e;} .pill-bad{background:#fee2e2;color:#991b1b;}

/* ---------- Hero ---------- */
.hero{background:linear-gradient(120deg,var(--forest-dark),var(--forest) 55%,var(--emerald-dark));border-radius:22px;padding:2rem 2.2rem;color:#ffffff;margin-bottom:1.4rem;box-shadow:0 10px 30px rgba(13,47,32,.18);}
.hero h1{color:#ffffff;font-size:2.1rem;margin:.6rem 0 .3rem;font-weight:800;letter-spacing:-.02em;padding:0;}
.hero p{color:#d5efe2;margin:0;font-size:1.02rem;max-width:780px;}
.hero-badge{background:rgba(255,255,255,.16);border-radius:999px;padding:.25rem .8rem;font-size:.72rem;font-weight:700;letter-spacing:.08em;}

/* ---------- Section titles ---------- */
.section-title{font-size:1.3rem;font-weight:700;color:var(--forest);margin:1.8rem 0 .2rem;}
.section-sub{color:var(--muted);font-size:.9rem;margin-bottom:.9rem;}

/* ---------- Cards ---------- */
.metric-card{background:#ffffff;border:1px solid var(--border);border-top:4px solid var(--emerald);border-radius:18px;padding:1.1rem 1.25rem;box-shadow:0 2px 10px rgba(20,69,47,.06);height:100%;}
.metric-card.warn{border-top-color:#f59e0b;} .metric-card.danger{border-top-color:#dc2626;}
.metric-label{font-size:.75rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:700;}
.metric-value{font-size:1.9rem;font-weight:800;color:var(--forest);line-height:1.25;margin-top:.2rem;}
.metric-caption{font-size:.8rem;color:var(--muted);margin-top:.1rem;}
.info-card{background:#ffffff;border:1px solid var(--border);border-radius:18px;padding:1.2rem 1.4rem;box-shadow:0 2px 10px rgba(20,69,47,.06);height:100%;}
.info-card h4{margin:0 0 .7rem;color:var(--forest);font-size:1.05rem;font-weight:700;padding:0;}
.info-row{display:flex;justify-content:space-between;gap:1rem;padding:.55rem 0;border-bottom:1px solid #eef2ec;font-size:.9rem;}
.info-row:last-child{border-bottom:none;}
.info-key{color:var(--muted);font-weight:500;flex-shrink:0;}
.info-val{color:var(--ink);font-weight:600;text-align:right;word-break:break-word;}
.info-val.na{color:#9aa8a0;font-weight:400;font-style:italic;}
.step-card{background:#ffffff;border:1px solid var(--border);border-radius:18px;padding:1.3rem;height:100%;box-shadow:0 2px 10px rgba(20,69,47,.06);}
.step-card .icon{font-size:1.7rem;} .step-card h4{margin:.4rem 0 .3rem;color:var(--forest);font-size:1.02rem;padding:0;}
.step-card p{margin:0;color:var(--muted);font-size:.88rem;}
.dl-card{background:#ffffff;border:1px solid var(--border);border-radius:18px;padding:1.2rem 1.4rem;margin-bottom:.8rem;box-shadow:0 2px 10px rgba(20,69,47,.06);}
.dl-card h4{margin:0 0 .2rem;color:var(--forest);padding:0;font-size:1.05rem;} .dl-card p{margin:0;color:var(--muted);font-size:.88rem;}

/* ---------- ESG indicator chips ---------- */
.chip{display:inline-block;padding:.22rem .75rem;border-radius:999px;font-size:.78rem;font-weight:700;margin:0 .4rem .4rem 0;border:1px solid transparent;}
.chip-env{background:#d1fae5;color:#065f46;border-color:#a7f3d0;}
.chip-soc{background:#fef3c7;color:#92400e;border-color:#fde68a;}
.chip-gov{background:#e0ece7;color:#14452f;border-color:#bfd5cb;}
.rule-list{color:var(--ink);font-size:.88rem;line-height:1.7;margin:0;padding-left:1.1rem;}

/* ---------- Text viewer ---------- */
.page-badge{background:var(--mint);color:var(--forest);border-radius:12px;padding:.55rem .9rem;font-size:.88rem;font-weight:600;margin:.6rem 0;}
.text-viewer{background:#ffffff;border:1px solid var(--border);border-radius:14px;padding:1.2rem 1.4rem;max-height:520px;overflow-y:auto;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.84rem;line-height:1.65;color:var(--ink);}
.text-viewer mark{background:#a7f3d0;color:var(--forest-dark);padding:0 3px;border-radius:4px;font-weight:700;}

/* ---------- Streamlit widgets ---------- */
[data-testid="stFileUploaderDropzone"], [data-testid="stFileUploadDropzone"]{background:#ffffff;border:2px dashed var(--emerald);border-radius:18px;padding:1.8rem;}
[data-testid="stFileUploaderDropzone"]:hover, [data-testid="stFileUploadDropzone"]:hover{background:#f0fdf6;}
.stButton>button, .stDownloadButton>button{background:var(--emerald-dark);border:none;border-radius:12px;font-weight:600;padding:.55rem 1.2rem;}
.stButton>button *, .stDownloadButton>button *{color:#ffffff !important;}
.stButton>button:hover, .stDownloadButton>button:hover{background:var(--forest);}
.stButton>button:disabled, .stDownloadButton>button:disabled{background:#c9d3cd;}
.stTabs [data-baseweb="tab-list"]{gap:.4rem;background:#ffffff;border-radius:14px;padding:.35rem;border:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{border-radius:10px;padding:.5rem 1rem;font-weight:600;}
.stTabs [aria-selected="true"]{background:var(--mint);}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{display:none;}
[data-testid="stAlert"]{border-radius:14px;}
[data-testid="stDataFrame"]{border-radius:14px;overflow:hidden;border:1px solid var(--border);}
</style>
"""


# =============================================================================
# 3. SMALL HELPER FUNCTIONS
# =============================================================================
def esc(value) -> str:
    """HTML-escape a value (also neutralises '$' so Markdown never treats it as LaTeX)."""
    return html.escape(str(value)).replace("$", "&#36;")


def to_html_text(text: str) -> str:
    """Escape text and convert new lines to <br> so Markdown cannot break the HTML block."""
    return esc(text.replace("\r", "")).replace("\n", "<br>")


def html_block(markup: str) -> str:
    """Collapse multi-line HTML into one line (blank lines would end a Markdown HTML block)."""
    return "".join(line.strip() for line in markup.splitlines())


def format_file_size(size_bytes: int) -> str:
    """Human readable file size."""
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def format_pdf_date(raw_date) -> str:
    """Convert a PDF date string such as D:20240131120000+05'30' into '31 Jan 2024'."""
    if not raw_date:
        return NOT_AVAILABLE
    match = re.match(r"D:(\d{4})(\d{2})?(\d{2})?", raw_date)
    if not match:
        return str(raw_date)
    try:
        year, month, day = (int(g) if g else 1 for g in match.groups())
        return datetime(year, month, day).strftime("%d %b %Y")
    except ValueError:
        return str(raw_date)


def clean_meta(value) -> str:
    """Return a stripped metadata value or 'Not available' if missing/blank."""
    value = (value or "").strip()
    return value if value else NOT_AVAILABLE


def format_page_ranges(numbers) -> str:
    """Compress [1,2,3,7,9,10] into '1–3, 7, 9–10'."""
    ranges, start, prev = [], None, None
    for n in numbers:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            ranges.append((start, prev))
            start = prev = n
    if start is not None:
        ranges.append((start, prev))
    text = ", ".join(str(a) if a == b else f"{a}–{b}" for a, b in ranges)
    return text if len(text) <= 250 else text[:247] + "…"


def metric_card(label, value, caption="", tone="") -> str:
    return html_block(
        f'<div class="metric-card {tone}"><div class="metric-label">{esc(label)}</div>'
        f'<div class="metric-value">{esc(value)}</div>'
        f'<div class="metric-caption">{esc(caption)}</div></div>'
    )


def info_card(title, rows) -> str:
    body = ""
    for key, value in rows:
        na_class = " na" if value == NOT_AVAILABLE else ""
        body += (
            f'<div class="info-row"><span class="info-key">{esc(key)}</span>'
            f'<span class="info-val{na_class}">{esc(value)}</span></div>'
        )
    return html_block(f'<div class="info-card"><h4>{esc(title)}</h4>{body}</div>')


def section_title(title, subtitle=""):
    st.markdown(
        html_block(
            f'<div class="section-title">{esc(title)}</div>'
            f'<div class="section-sub">{esc(subtitle)}</div>'
        ),
        unsafe_allow_html=True,
    )


def show_table(df: pd.DataFrame, height=None, column_config=None):
    """Display a DataFrame without the row index (works with old and new Streamlit versions)."""
    options = {"hide_index": True, "height": height}
    if column_config:
        options["column_config"] = column_config
    try:
        st.dataframe(df, width="stretch", **options)
    except Exception:
        try:
            st.dataframe(df, use_container_width=True, **options)
        except Exception:
            st.dataframe(df.reset_index(drop=True), use_container_width=True, height=height)


# =============================================================================
# 4. RULE-BASED ESG TAXONOMY (25 INDICATORS)
# =============================================================================
# Each ESG indicator is described by regular-expression groups:
#   anchors : specific phrases that are strong evidence on their own
#             (e.g. "scope 1", "lost time injury frequency rate", "water withdrawal").
#   terms   : weaker, generic words (e.g. "water", "employees", "recall").
#             They only count when several co-occur (3+) or when combined with an
#             anchor / "evidence words" (numbers, %, targets, policies ...).
#   exclude : phrases that signal a false positive (e.g. "waterproof", "cash
#             withdrawal", "inventory turnover"). A window containing one of them
#             is ignored for that indicator.
#   require : (optional) context words that MUST appear in the same window for
#             the indicator to count at all (e.g. waste diversion needs the word
#             "waste"; anti-corruption incidents need "cases/complaints/fines ...").
#             This is what separates a policy statement from a reported data point.
#
# Terminology covered: Indian BRSR (SEBI), GRI 2/3xx/4xx and ESRS E1-E5, S1, S4, G1.
class EsgRule:
    """One ESG indicator with its compiled keyword rules."""

    def __init__(self, category, indicator, anchors, terms=(), exclude=(), require=None):
        self.category = category
        self.indicator = indicator
        self.anchors = self._join(anchors)
        self.terms = [re.compile(pattern, re.IGNORECASE) for pattern in terms]
        self.exclude = self._join(exclude)
        self.require = re.compile(require, re.IGNORECASE) if require else None

    @staticmethod
    def _join(patterns):
        if not patterns:
            return None
        return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


# Words that show a sentence is reporting facts/actions (numbers, units, targets, policies ...).
EVIDENCE_PATTERN = re.compile(
    r"\d\s?%|\bper ?cent\b|\d{1,3}(?:,\d{3})+"
    r"|\b\d+(?:\.\d+)?\s?(?:tonnes?|tons?|kwh|mwh|gwh|gj|tj|kl|m3|hours|mt|lakhs?|crores?|million|billion)\b"
    r"|\b(?:targets?|reduc\w*|increas\w*|decreas\w*|improv\w*|polic(?:y|ies)|programmes?|programs?"
    r"|initiatives?|committee|framework|disclos\w*|certified|certification|audit\w*|monitor\w*"
    r"|committed|commitment|implement\w*|measures?|tco2\w*|kwh|mwh|gigajoules?|tonnes?)\b",
    re.IGNORECASE,
)

# Shared "context" requirements (kept as constants so the rules below stay readable).
REQ_EMISSIONS = r"emission|ghg|greenhouse|co2|carbon|footprint"
REQ_WASTE = r"\bwaste|\bscrap\b|\bresidues?\b|\bsludge\b|\bfly ash\b|\bslag\b"
REQ_ETHICS = r"corrupt|brib|ethic|code of conduct|integrity|anti-?fraud"
REQ_COMPLAINT = r"\b(?:complaints?|cases?|received|resolved|pending|allegations?|disposed|raised|reports? of)\b"
REQ_INCIDENT = (r"\b(?:incidents?|cases?|instances?|complaints?|charges?|allegations?|convictions?|fines?"
                r"|penalt\w+|disciplinary|dismissed|terminated|reported|nil|zero|none|no)\b")
REQ_NUMBER = r"\d"

ESG_RULES = [
    # ------------------------------------------------------------------ ENVIRONMENTAL (11)
    # 1 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Scope 1 GHG Emissions",
        anchors=[
            r"\bscope[\s-]*(?:1|one)\b",                                  # "Scope 1", "Scope-1"
            r"\bdirect (?:ghg |greenhouse gas |carbon )?emissions\b",     # GRI 305-1 wording
            r"\b(?:stationary|mobile) combustion\b", r"\bfugitive emissions\b",
            r"\bemissions? from (?:owned|controlled|company[- ]owned) (?:sources|operations|facilities|vehicles|fleet)\b",
            r"\bgri\s?305-1\b",
        ],
        terms=[r"\bcombustion\b", r"\brefrigerants?\b", r"\bdiesel\b", r"\bon-?site (?:fuel|generation)\b",
               r"\b(?:tco2e?|tonnes? of co2|mtco2e?)\b", r"\bemissions?\b"],
        require=REQ_EMISSIONS,
    ),
    # 2 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Scope 2 GHG Emissions",
        anchors=[
            r"\bscope[\s-]*(?:2|two)\b",
            r"\bscope[\s-]*1\s*(?:,|and|&|\+|/)\s*(?:scope\s*)?2\b",      # "Scope 1 and 2"
            r"\bscope[\s-]*1\s*(?:,|and|&|\+|/)\s*(?:scope\s*)?2\s*(?:,|and|&|\+|/)\s*(?:scope\s*)?3\b",
            r"\benergy indirect\b", r"\bindirect (?:ghg |greenhouse gas |carbon )?emissions\b",
            r"\blocation[- ]based (?:method|emissions|approach|scope|figure)\b",
            r"\bmarket[- ]based (?:method|emissions|approach|scope|figure)\b",
            r"\bemissions? (?:from|due to|associated with|related to) (?:the )?(?:purchased|consumption of|imported) "
            r"(?:electricity|energy|power|steam|heat\w*|cooling)\b",
            r"\bgri\s?305-2\b",
        ],
        terms=[r"\bpurchased (?:electricity|energy|power|steam)\b", r"\bgrid emission factors?\b",
               r"\bemission factors?\b", r"\b(?:tco2e?|tonnes? of co2|mtco2e?)\b", r"\bemissions?\b"],
        require=REQ_EMISSIONS,
    ),
    # 3 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Scope 3 GHG Emissions",
        anchors=[
            r"\bscope[\s-]*(?:3|three)\b",
            r"\bscope[\s-]*1\s*(?:-|to)\s*3\b",
            r"\bvalue[- ]chain (?:ghg |greenhouse gas |carbon )?emissions\b",
            r"\bsupply[- ]chain (?:ghg |greenhouse gas |carbon )?emissions\b",
            r"\b(?:upstream|downstream|other indirect) (?:ghg |greenhouse gas )?emissions\b",
            r"\bghg protocol corporate value chain\b", r"\bgri\s?305-3\b",
        ],
        terms=[r"\bbusiness travel\b", r"\bemployee commuting\b", r"\bpurchased goods(?: and services)?\b",
               r"\b(?:upstream|downstream) transportation\b", r"\buse of sold products\b",
               r"\bend[- ]of[- ]life treatment\b", r"\bcapital goods\b", r"\bvalue chain\b"],
        require=REQ_EMISSIONS,
    ),
    # 4 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Total Energy Consumption",
        anchors=[
            r"\btotal (?:energy|electricity|fuel) (?:consumption|consumed|use|usage)\b",   # BRSR (A+B+C)
            r"\benergy (?:consumption|consumed|intensity|use|usage|mix|demand)\b",
            r"\b(?:electricity|fuel|power|diesel|natural gas) (?:consumption|consumed)\b",
            r"\bconsumption of (?:electricity|energy|fuel|power)\b",
            r"\benergy (?:from|through) (?:other|non-renewable|renewable) sources\b",
            r"\benergy consumed within the organi[sz]ation\b",
            r"\biso\s?50001\b", r"\bgri\s?302(?:-\d)?\b",
        ],
        terms=[r"\benergy\b", r"\belectricity\b", r"\bfuel\b", r"\bconsumption\b",
               r"\b(?:kwh|mwh|gwh|twh|gj|tj|gigajoules?|terajoules?|petajoules?)\b",
               r"\benergy (?:efficiency|saving|savings|conservation)\b"],
        exclude=[r"\b(?:energy|power) (?:sector|segment|industry|business|companies|projects?|exchange|trading)\b",
                 r"\benergy drinks?\b", r"\boil (?:and|&) gas\b"],
    ),
    # 5 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Renewable Energy Share",
        anchors=[
            r"\b(?:share|percentage|proportion|mix|%) of (?:total )?(?:energy|electricity|power)? ?(?:from |sourced from )?renewable\w*",
            r"\brenewable (?:energy|electricity|power) (?:consumption|consumed|usage|use|procurement|purchased|"
            r"generated|generation|sourcing|sourced|capacity|mix|share|percentage|certificates?)\b",
            r"\b(?:energy|electricity|power) (?:from|through|sourced from) renewable (?:sources|energy)\b",
            r"\bfrom renewable (?:sources|energy)\b",
            r"\b(?:solar|wind|hydro\w*|biomass|biogas) (?:power|energy|electricity) (?:consumed|consumption|generation|generated|purchased|capacity)\b",
            r"\brenewable energy certificates?\b", r"\bre100\b", r"\bpower purchase agreements?\b",
            r"\bcaptive (?:solar|wind|renewable)\b", r"\bgreen (?:power|energy|electricity)\b",
        ],
        terms=[r"\brenewable\w*", r"\bsolar\b", r"\bwind\b", r"\bhydro\w*", r"\bbiomass\b", r"\bclean energy\b"],
        exclude=[r"\bwind(?:ing)?[- ]up\b", r"\brenewable (?:contracts?|lease|term|premium|licen[cs]e|subscription)\b"],
    ),
    # 6 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Water Withdrawal",
        anchors=[
            r"\bwater (?:withdrawals?|withdrawn|drawn|abstraction)\b",
            r"\b(?:withdrawal|abstraction) of (?:fresh |ground |surface )?water\b",
            r"\btotal volume of water (?:withdrawal|withdrawn|drawn)\b",
            r"\bwater withdrawal by source\b",
            r"\b(?:fresh ?water|groundwater|surface water) (?:withdrawals?|withdrawn|drawn)\b",
            r"\bgri\s?303-3\b",
        ],
        terms=[r"\bsurface water\b", r"\bground ?water\b", r"\bthird[- ]party water\b",
               r"\bsea ?water\b|\bdesalinated\b", r"\bkilolit(?:re|er)s?\b|\bkl\b", r"\bwater (?:source|sources)\b"],
        exclude=[r"\bwater(?:-| )?(?:proof|tight|mark|fall|front|colou?r|melon|park|sports)\b",
                 r"\bcash withdrawal\b", r"\bwithdrawal of (?:the )?(?:offer|appeal|petition|application|funds)\b"],
    ),
    # 7 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Water Consumption",
        anchors=[
            r"\bwater (?:consumption|consumed|intensity|footprint|usage|use)\b",
            r"\btotal (?:volume of )?water (?:consumed|consumption|used)\b",
            r"\bnet water (?:consumption|use)\b", r"\bwater consumption intensity\b",
            r"\bwater (?:recycled|reused|recycling|reuse|stress\w*|stewardship|neutral\w*|positive)\b",
            r"\bzero liquid discharge\b", r"\bgri\s?303-5\b",
        ],
        terms=[r"\bwater\b", r"\bconsum\w+", r"\brecycl\w+", r"\bdischarge\b",
               r"\bkilolit(?:re|er)s?\b|\bm3\b|\bcubic met(?:re|er)s?\b", r"\bintensity\b"],
        exclude=[r"\bwater(?:-| )?(?:proof|tight|mark|fall|front|colou?r|melon|park|sports)\b",
                 r"\bunder water\b"],
    ),
    # 8 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Waste Generated",
        anchors=[
            r"\bwaste (?:generated|generation|produced|arising|quantity|volumes?|footprint|intensity)\b",
            r"\btotal (?:amount of )?waste\b",
            r"\b(?:hazardous|non-hazardous|nonhazardous|plastic|bio-?medical|battery|radioactive|electronic|industrial|"
            r"solid|municipal|food|e|construction (?:and|&) demolition) waste\b",   # BRSR waste categories (A)-(H)
            r"\bgri\s?306-3\b",
        ],
        terms=[r"\bwaste\b(?!\s?-?water)", r"\b(?:metric )?tonnes?\b|\bmt\b", r"\bgenerat\w+",
               r"\bsludge\b", r"\bfly ash\b|\bslag\b", r"\bscrap\b"],
        exclude=[r"\bfraud,? waste\b", r"\bwaste (?:of|and abuse|,? abuse)\b", r"\bwaste(?:d)? (?:time|money|effort)\b"],
    ),
    # 9 ------------------------------------------------------------------
    EsgRule(
        "Environmental", "Waste Diverted from Disposal",
        anchors=[
            r"\bwaste (?:diverted|diversion|recovered|recycled|reused|re-used|recovery)\b",
            r"\b(?:diverted|diversion) (?:from|away from) (?:disposal|landfills?)\b",
            r"\b(?:recycling|re-?using|reuse|other recovery|recovery) operations\b",       # BRSR wording
            r"\bpreparation for (?:re-?use|recycling)\b",
            r"\bwaste[- ]to[- ]energy\b", r"\bco-?processing\b", r"\bcompost(?:ing|ed)?\b",
            r"\blandfill (?:diversion|avoidance)\b", r"\bzero (?:waste to )?landfill\b",
            r"\brecycl\w+ (?:rate|of waste)\b", r"\bgri\s?306-4\b",
        ],
        terms=[r"\brecycl\w+", r"\bre-?us\w+", r"\brecover\w+", r"\bcompost\w*", r"\blandfill\w*",
               r"\bincinerat\w+", r"\bdisposal\b"],
        require=REQ_WASTE,
    ),
    # 10 -----------------------------------------------------------------
    EsgRule(
        "Environmental", "Air Pollutant Emissions",
        anchors=[
            r"\bair (?:emissions|pollutants?|pollution|quality)\b", r"\bambient air\b",
            r"(?-i:\bNOx\b)", r"(?-i:\bSOx\b)", r"\bnitrogen oxides?\b", r"\bsulph?ur (?:dioxide|oxides?)\b",
            r"\bparticulate matter\b", r"(?-i:\bPM\s?(?:2\.5|10)\b)", r"\bsuspended particulate\b",
            r"\bvolatile organic compounds?\b", r"(?-i:\bVOCs?\b)", r"\bpersistent organic pollutants?\b",
            r"\bhazardous air pollutants?\b", r"\bstack emissions?\b", r"\bozone[- ]depleting\b",
            r"\bgri\s?305-7\b",
        ],
        terms=[r"\bpollut\w+", r"\bstack\b", r"\bdust\b", r"\bflue gas\b", r"\bemissions?\b",
               r"\bmonitoring\b", r"\bspm\b"],
        exclude=[r"\bsarbanes\b", r"\bsox (?:compliance|controls?|audit|404)\b"],
    ),
    # 11 -----------------------------------------------------------------
    EsgRule(
        "Environmental", "Biodiversity Impacts",
        anchors=[
            r"\bbiodiversity (?:impacts?|loss|risks?|assessments?|footprint|hotspots?|management|action plan|"
            r"conservation|protection|sensitive|value|net gain)\b",
            r"\bimpacts? (?:on|to) biodiversity\b", r"\becologically sensitive (?:areas?|zones?)\b",
            r"\b(?:protected|conservation) areas?\b", r"\bnational parks?\b", r"\bwildlife sanctuar(?:y|ies)\b",
            r"\bbiosphere reserves?\b", r"\bareas? of high biodiversity\b",
            r"\b(?:iucn red list|endangered species|threatened species)\b",
            r"\bhabitat (?:loss|destruction|restoration|degradation|fragmentation)\b",
            r"\bdeforestation\b", r"\bland[- ]use change\b", r"\bnature[- ](?:related|positive)\b", r"\btnfd\b",
            r"\bgri\s?304(?:-\d)?\b",
        ],
        terms=[r"\bbiodiversity\b", r"\bhabitats?\b", r"\bspecies\b", r"\bwetlands?\b", r"\bmangroves?\b",
               r"\bforests?\b", r"\benvironmental impact assessments?\b|\beia\b", r"\becosystems?\b"],
        exclude=[r"\b(?:digital|business|partner|innovation|startup|start-up|payments?|developer|technology|"
                 r"financial|customer|app) ecosystems?\b", r"\becosystem of (?:partners|developers|apps)\b"],
    ),

    # ------------------------------------------------------------------ SOCIAL (8)
    # 12 -----------------------------------------------------------------
    EsgRule(
        "Social", "Total Workforce",
        anchors=[
            r"\btotal (?:number of )?(?:employees|workers|workforce|headcount|staff)\b",
            r"\b(?:employee|workforce|staff) (?:headcount|count|strength|profile|composition|demographics|breakdown)\b",
            r"\bnumber of (?:permanent |full[- ]time |part[- ]time |contract(?:ual)? |temporary |other than permanent )?"
            r"(?:employees|workers|staff)\b",
            r"\b(?:permanent|full[- ]time|part[- ]time|temporary|fixed[- ]term|non[- ]guaranteed hours|"
            r"other than permanent|contract(?:ual)?|differently abled) (?:employees|workers|staff|workforce)\b",
            r"\bheadcount\b", r"(?-i:\bFTEs?\b)", r"\bfull[- ]time equivalents?\b",
            r"\bemployees and workers\b", r"\bworkers who are not employees\b", r"\bgri\s?2-(?:7|8)\b",
        ],
        terms=[r"\bemployees\b", r"\bworkers\b", r"\bworkforce\b", r"\bstaff\b",
               r"\bpermanent\b", r"\bcontract(?:ual)?\b", r"\bas (?:on|at) 31\b"],
        exclude=[r"\b(?:esops?|employee stock|share[- ]based|stock options?|post[- ]employment|defined benefit|"
                 r"gratuity|actuarial|provident fund|employee benefits? expense)\b"],
        require=REQ_NUMBER,
    ),
    # 13 -----------------------------------------------------------------
    EsgRule(
        "Social", "Gender Diversity",
        anchors=[
            r"\bgender (?:diversity|ratio|balance|parity|equality|split|distribution|representation|pay gap)\b",
            r"\b(?:female|women) (?:employees|workers|workforce|representation|staff|hires?|talent|participation)\b",
            r"\b(?:percentage|proportion|share|number) of (?:women|females?)\b",
            r"\brepresentation of (?:women|females?)\b", r"\bwomen (?:in|on) (?:the )?(?:workforce|board|leadership|"
            r"management|senior management)\b",
            r"\bmale and female\b", r"\bfemale\s*\(\s*(?:%|b/a|d/c)", r"\bdiversity,? equity,? (?:and|&) inclusion\b",
            r"\bdiversity (?:and|&) inclusion\b", r"\bgri\s?405(?:-\d)?\b",
        ],
        terms=[r"\bwomen\b|\bfemales?\b", r"\bgender\b", r"\bmales?\b", r"\bdiversity\b", r"\binclusi\w+",
               r"\bequal opportunit(?:y|ies)\b"],
        exclude=[r"\bdiversity of (?:products?|portfolio|businesses|revenue|income|customers?|investments?|assets?|"
                 r"funding|suppliers?|sources?|offerings?|loans?)\b",
                 r"\b(?:portfolio|product|revenue|income|geographic|geographical|business) diversity\b"],
    ),
    # 14 -----------------------------------------------------------------
    EsgRule(
        "Social", "Employee Turnover Rate",
        anchors=[
            r"\b(?:employee|staff|workforce|worker|talent) (?:turnover|attrition)\b",
            r"\bturnover rate (?:for|of|among) (?:permanent )?(?:employees|workers|staff)\b",   # BRSR wording
            r"\b(?:voluntary|involuntary|regretted) (?:turnover|attrition)\b",
            r"\battrition (?:rate|of employees)\b", r"\bemployee (?:separations?|exits?)\b",
            r"\bnew (?:employee )?hires and (?:employee )?turnover\b", r"\bgri\s?401-1\b",
        ],
        terms=[r"\battrition\b", r"\bresign\w+", r"\bseparations?\b", r"\bnew hires?\b", r"\bemployees\b",
               r"\bleavers?\b|\bemployees? (?:who )?left\b"],
        exclude=[r"\b(?:inventory|asset|receivables?|debtors?|stock) turnover\b"],
    ),
    # 15 -----------------------------------------------------------------
    EsgRule(
        "Social", "Employee Training Hours",
        anchors=[
            r"\b(?:average )?(?:hours|days|man[- ]?hours|man[- ]?days|person[- ]?days) of (?:training|learning)\b",
            r"\b(?:training|learning) (?:hours|man[- ]?hours|man[- ]?days|person[- ]?days|coverage)\b",
            r"\baverage (?:training|learning) (?:hours|days)\b",
            r"\b(?:employees|workers|staff|workforce)(?: and workers)? (?:were |was |who )?(?:trained|received training)\b",
            r"\b(?:trained|training) (?:employees|workers)\b", r"\bpercentage of (?:employees|workers) trained\b",
            r"\b(?:skill upgradation|up-?skilling|re-?skilling)\b",
            r"\b(?:training|learning) (?:and|&) development\b", r"\bgri\s?404-1\b",
        ],
        terms=[r"\btraining\b", r"\btrained\b", r"\bemployees\b", r"\bworkers\b", r"\blearning\b",
               r"\bskills?\b", r"\bhours\b"],
        exclude=[r"\b(?:training|trained) (?:data|dataset|set|model|models|algorithm)\b",
                 r"\bmachine learning\b", r"\bdeep learning\b"],
    ),
    # 16 -----------------------------------------------------------------
    EsgRule(
        "Social", "Work-related Injury Rate",
        anchors=[
            r"\b(?:ltifr|trifr|ltir|trir)\b", r"\blost[- ]time (?:injur\w+|incidents?|accidents?|frequency)\b",
            r"\b(?:total )?recordable (?:work[- ]related )?(?:injur\w+|incidents?|cases?|accidents?)\b",
            r"\b(?:injury|accident) (?:frequency|rate|severity)\b", r"\bfrequency rate\b",
            r"\bhigh[- ]consequence work[- ]related\b", r"\bwork[- ]related (?:injur\w+|ill[- ]?health|accidents?)\b",
            r"\bper (?:one )?(?:million|200,?000|1,?000,?000)[- ]?(?:person[- ]?|man[- ]?)?hours\b",
            r"\breportable (?:injur\w+|accidents?)\b", r"\bfirst[- ]aid cases?\b", r"\bgri\s?403-9\b",
        ],
        terms=[r"\binjur\w+", r"\baccidents?\b", r"\blost[- ]time\b", r"\b(?:person|man)[- ]?hours\b",
               r"\bill[- ]?health\b", r"\bsafety\b"],
        exclude=[r"\bpersonal injury (?:claims?|lawsuits?|litigation)\b", r"\b(?:cyber|data|information|food|product|"
                 r"consumer|drug|patient|road) safety\b"],
    ),
    # 17 -----------------------------------------------------------------
    EsgRule(
        "Social", "Work-related Fatalities",
        anchors=[
            r"\bwork[- ]related (?:fatalit\w+|deaths?)\b", r"\b(?:workplace|occupational|on-?site|employee|worker) (?:fatalit\w+|deaths?)\b",
            r"\bfatalit(?:y|ies) (?:due to|from|resulting from|at|in) (?:work|the workplace|operations|accidents?)\b",
            r"\b(?:number of|no\. of|total) fatalit(?:y|ies)\b", r"\bfatal (?:accidents?|injur\w+|incidents?)\b",
            r"\bzero fatalit(?:y|ies)\b", r"\bfatality (?:rate|frequency)\b", r"\bloss of (?:life|lives)\b",
            r"\bdeaths? of (?:an? |our )?(?:employee|worker|contractor|workers|employees|contractors)\b",
            r"\bgri\s?403-9\b",
        ],
        terms=[r"\bfatalit\w+", r"\bdeaths?\b", r"\bfatal\b", r"\bworkers?\b|\bemployees?\b|\bcontractors?\b",
               r"\bincidents?\b|\baccidents?\b"],
        exclude=[r"\broad (?:accident|fatalit|traffic)\w*", r"\bcovid\b", r"\bpandemic\b",
                 r"\bdeath benefits?\b", r"\bdeath gratuity\b"],
    ),
    # 18 -----------------------------------------------------------------
    EsgRule(
        "Social", "Human Rights Assessments",
        anchors=[
            r"\bhuman rights? (?:impact |risk )?(?:assessments?|due diligence|reviews?|audits?|screening)\b",
            r"\bassessments? (?:of|on|for) human rights?\b",
            r"\b(?:assessed|reviewed|screened|audited) (?:for|on) (?:human rights?|child labou?r|forced labou?r)\b",
            r"\b(?:plants?|offices?|operations|sites?|locations?)(?: and offices)? (?:that )?(?:were |was |have been )?"
            r"(?:assessed|reviewed|subject to) .{0,40}(?:human rights?|child labou?r|forced labou?r)",
            r"\bhuman rights? (?:violations?|grievances?|incidents?|complaints?|impacts?)\b",
            r"\bun guiding principles\b|\bungp\b", r"\bgri\s?412(?:-\d)?\b",
        ],
        terms=[r"\bhuman rights?\b", r"\bchild labou?r\b", r"\bforced labou?r\b|\binvoluntary labou?r\b",
               r"\bdiscrimination\b", r"\bsexual harassment\b", r"\bassess\w+", r"\bdue diligence\b",
               r"\bwages?\b", r"\bmodern slavery\b"],
    ),
    # 19 -----------------------------------------------------------------
    EsgRule(
        "Social", "Product Safety Incidents",
        anchors=[
            r"\bproduct (?:safety|quality) (?:incidents?|issues?|complaints?|concerns?|recalls?|non[- ]?compliances?|"
            r"failures?|events?|alerts?)\b",
            r"\bproduct (?:recalls?|liability claims?)\b", r"\b(?:voluntary|forced|mandatory|safety) recalls?\b",
            r"\brecalls? (?:of|on account of|due to) (?:products?|safety|quality|defects?)\b",
            r"\b(?:health and safety|safety) (?:impacts?|incidents?|issues?) (?:of|related to|concerning|associated with) "
            r"(?:our )?(?:products?|services?)\b",
            r"\bincidents? of non[- ]?compliance concerning (?:the )?(?:health and safety|product)\b",
            r"\bfood safety (?:incidents?|recalls?|complaints?|issues?)\b",
            r"\bconsumer safety\b", r"\bcustomer (?:health and )?safety\b", r"\bgri\s?416(?:-\d)?\b",
        ],
        terms=[r"\brecalls?\b", r"\bdefects?\b", r"\b(?:consumer|customer) complaints?\b", r"\bproduct safety\b",
               r"\bsafety (?:issues?|concerns?)\b", r"\badverse events?\b"],
    ),

    # ------------------------------------------------------------------ GOVERNANCE (6)
    # 20 -----------------------------------------------------------------
    EsgRule(
        "Governance", "Board Independence",
        anchors=[
            r"\bindependent (?:non[- ]executive )?directors?\b", r"\b(?:percentage|proportion|share|number|ratio) of independent\b",
            r"\bboard independence\b", r"\bindependence of (?:the )?(?:board|directors?)\b",
            r"\bindependent (?:board members?|members? of the board|chair(?:man|person)?|majority)\b",
            r"\bindependent non[- ]executive\b", r"\bindependence criteria\b",
            r"\bdeclarations? (?:of|on) independence\b", r"\bgri\s?2-9\b",
        ],
        terms=[r"\bindependence\b(?!\s+of\s+(?:the\s+)?(?:statutory |external |internal )?auditors?)",
               r"\bnon[- ]executive\b", r"\bboard of directors\b", r"\bdirectors\b",
               r"\bsebi\b|\blisting regulations\b|\blodr\b", r"\bboard\b"],
    ),
    # 21 -----------------------------------------------------------------
    EsgRule(
        "Governance", "Anti-corruption Incidents",
        anchors=[
            r"\b(?:confirmed )?(?:incidents?|cases?|instances?) of (?:corruption|bribery)\b",
            r"\b(?:corruption|bribery)[- ](?:related )?(?:incidents?|cases?|charges|allegations|complaints|convictions|investigations?)\b",
            r"\b(?:charges?|allegations?|convictions?) (?:of|for|related to|relating to) (?:bribery|corruption)\b",
            r"\b(?:fines?|penalt(?:y|ies)|settlements?) (?:for|related to|relating to|in connection with) (?:bribery|corruption)\b",
            r"\bdisciplinary action\b[^.]{0,120}\b(?:bribery|corruption)\b",
            r"\bagainst whom disciplinary action\b", r"\bterminated for (?:corruption|bribery)\b", r"\bgri\s?205-3\b",
        ],
        terms=[r"\bcorruption\b", r"\bbribery\b", r"\bfraud\b", r"\bdisciplinary\b",
               r"\blaw enforcement\b", r"\bdismiss\w+|\bterminat\w+"],
        exclude=[r"\b(?:data|file|memory|disk|database|system) corruption\b", r"\bcorrupt(?:ed)? (?:file|data|pdf)\b"],
        require=REQ_INCIDENT,
    ),
    # 22 -----------------------------------------------------------------
    EsgRule(
        "Governance", "Anti-corruption Training Coverage",
        anchors=[
            r"\banti[- ]?(?:corruption|bribery)(?: and (?:anti[- ]?)?(?:bribery|corruption))? "
            r"(?:training|awareness|e-?learning|programmes?|programs?|sessions?|modules?|courses?)\b",
            r"\b(?:training|awareness|trained|communicat\w+) (?:on|in|of|about|regarding) (?:the )?"
            r"(?:anti[- ]?)?(?:corruption|bribery|ethics|code of conduct|business ethics|integrity)\b",
            r"\bpercentage of (?:employees|persons|functions|business partners|directors|workers) (?:covered|trained)\b",
            r"\bawareness programmes? (?:held|conducted|on)\b", r"\b(?:ethics|code of conduct) training\b",
            r"\bgri\s?205-2\b",
        ],
        terms=[r"\btraining\b", r"\bawareness programmes?\b|\bawareness programs?\b", r"\btrained\b",
               r"\bcovered\b", r"\bpercentage\b|%", r"\bdirectors\b|\bkmps?\b|\bemployees\b|\bworkers\b"],
        require=REQ_ETHICS,
    ),
    # 23 -----------------------------------------------------------------
    EsgRule(
        "Governance", "Whistleblower Complaints",
        anchors=[
            r"\bwhistle[- ]?blower (?:complaints?|reports?|cases?|incidents?|concerns?|allegations?|hotline|helpline)\b",
            r"\bwhistle[- ]?blowing (?:complaints?|reports?|cases?|incidents?)\b",
            r"\b(?:complaints?|reports?|cases?|concerns?) (?:received|raised|reported|lodged|filed) "
            r"(?:under|through|via|on|to|by) (?:the )?(?:whistle|vigil|speak[- ]up|ethics|integrity)\w*",
            r"\bvigil mechanism (?:complaints?|cases?|reports?)\b", r"\bspeak[- ]?up (?:reports?|cases?|complaints?|hotline|helpline|line)\b",
            r"\b(?:ethics|integrity|compliance) (?:hotline|helpline) (?:complaints?|calls?|reports?|cases?)\b",
            r"\bnumber of (?:whistle[- ]?blower|vigil)\b",
        ],
        terms=[r"\bwhistle[- ]?blow\w*", r"\bvigil mechanism\b", r"\bspeak[- ]?up\b", r"\bethics (?:hotline|helpline)\b",
               r"\bcomplaints?\b", r"\b(?:received|resolved|pending|disposed)\b", r"\banonymous\b"],
        require=REQ_COMPLAINT,
    ),
    # 24 -----------------------------------------------------------------
    EsgRule(
        "Governance", "Regulatory Non-compliance Fines",
        anchors=[
            r"\b(?:regulatory|monetary|legal|significant|material) (?:fines?|penalt(?:y|ies)|sanctions?)\b",
            r"\bfines? (?:and|or|&|/) (?:penalt(?:y|ies)|sanctions?|settlements?)\b",
            r"\bpenalt(?:y|ies),? (?:and|or|&|/) (?:fines?|settlements?|compounding)\b",
            r"\bpenalty\s*/\s*fine\b", r"\bcompounding fees?\b",
            r"\bnon[- ]?compliance (?:with|of) (?:laws|regulations|environmental|statutory|applicable)\b",
            r"\b(?:fines?|penalt(?:y|ies)) (?:imposed|levied|paid|incurred|assessed|payable|received)\b",
            r"\b(?:imposed|levied|paid) (?:a |an )?(?:fines?|penalt(?:y|ies))\b",
            r"\bsignificant instances of non[- ]?compliance\b", r"\bgri\s?2-27\b",
        ],
        terms=[r"\bfines?\b(?!-)", r"\bpenalt(?:y|ies)\b", r"\bnon[- ]?compliances?\b",
               r"\b(?:regulatory|enforcement) (?:agenc\w+|author\w+|bod\w+)\b", r"\bsettlements?\b",
               r"\bshow[- ]cause notices?\b", r"\bcompounding\b"],
        exclude=[r"\b(?:income tax|gst|excise|customs duty|contingent liabilit\w+)\b",
                 r"\b(?:late payment|default|prepayment|lock-?in) penalt\w+", r"\bpenalty clauses?\b",
                 r"\bliquidated damages\b", r"\bpenal interest\b", r"\binterest and penalt\w+"],
    ),
    # 25 -----------------------------------------------------------------
    EsgRule(
        "Governance", "Supplier ESG Assessments",
        anchors=[
            r"\b(?:suppliers?|vendors?|supply[- ]chain|value[- ]chain partners?)(?:'s)? (?:esg|sustainability|social|environmental|"
            r"human rights) (?:assessments?|audits?|screening|evaluations?|due diligence|risk assessments?|scorecards?|ratings?)\b",
            r"\b(?:suppliers?|vendors?|value[- ]chain partners?|supply[- ]chain partners?)\s+(?:were |was |have been |has been )?"
            r"(?:\w+\s+){0,3}?(?:assessed|audited|screened|evaluated)\b",
            r"\b(?:assessments?|audits?|screening|evaluations?|assessed|audited|screened|evaluated) (?:of |on )?"
            r"(?:our |its |the |new |key |critical |tier[- ]?1 )*(?:suppliers?|vendors?|value[- ]chain partners?|supply[- ]chain partners?)\b",
            r"\bpercentage of (?:value[- ]chain partners|suppliers|vendors) (?:assessed|screened|audited)\b",
            r"\bnew suppliers (?:that were )?screened\b", r"\bgri\s?(?:308|414)(?:-\d)?\b",
        ],
        terms=[r"\bsuppliers?\b|\bvendors?\b", r"\bvalue[- ]chain partners?\b", r"\bassess\w+", r"\bscreen\w+",
               r"\bsupplier code of conduct\b", r"\besg\b|\bsustainability\b", r"\bcorrective action\b"],
        exclude=[r"\b(?:trade payables?|supplier finance|supplier credit|statutory audit|auditor'?s? report|"
                 r"key audit matters?|msme)\b"],
    ),
]

# Guard: the taxonomy must stay exactly at the 25 finalised indicators (11 + 8 + 6).
assert len(ESG_RULES) == 25, "The taxonomy must contain exactly 25 ESG indicators."
assert [sum(1 for r in ESG_RULES if r.category == c) for c in CATEGORY_ORDER] == [11, 8, 6], \
    "Expected 11 Environmental, 8 Social and 6 Governance indicators."

INDICATOR_ORDER = {rule.indicator: position for position, rule in enumerate(ESG_RULES)}
INDICATOR_CATEGORY = {rule.indicator: rule.category for rule in ESG_RULES}


# =============================================================================
# 5. PDF PROCESSING
# =============================================================================
class PDFProcessingError(Exception):
    """Raised with a user-friendly message when a PDF cannot be processed."""


def open_pdf(file_bytes: bytes) -> fitz.Document:
    """Open a PDF from bytes, raising friendly errors for invalid/corrupt/protected files."""
    if not file_bytes:
        raise PDFProcessingError("The uploaded file is empty (0 bytes).")
    if b"%PDF" not in file_bytes[:1024]:
        raise PDFProcessingError(
            "This file does not look like a valid PDF (missing PDF header). "
            "Please upload a genuine .pdf file."
        )
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFProcessingError(
            "The PDF appears to be corrupted or unreadable. "
            "Try re-downloading or re-exporting the file."
        ) from exc

    if document.needs_pass:
        document.close()
        raise PDFProcessingError(
            "This PDF is password-protected. Remove the password "
            "(or save an unprotected copy) and upload it again."
        )
    if document.page_count == 0:
        document.close()
        raise PDFProcessingError("The PDF contains no pages.")
    return document


def extract_document(file_bytes: bytes, progress_bar) -> dict:
    """
    Extract text page by page (original PDF page numbers are kept), then run the
    rule-based ESG detection. The progress bar covers both stages.
    """
    document = open_pdf(file_bytes)
    try:
        total_pages = document.page_count
        metadata = document.metadata or {}

        pages = []
        for index in range(total_pages):
            page_number = index + 1  # original PDF page number
            extraction_error = False
            try:
                text = document.load_page(index).get_text("text") or ""
            except Exception:  # a single bad page must not stop the whole run
                text, extraction_error = "", True

            has_text = bool(text.strip())
            if extraction_error:
                status = "Extraction error"
            elif has_text:
                status = "Text extracted"
            else:
                status = "No selectable text"

            pages.append({
                "number": page_number,
                "text": text,
                "chars": len(text),
                "words": len(text.split()),
                "has_text": has_text,
                "status": status,
                "esg": [],  # filled by analyse_esg()
            })
            progress_bar.progress(
                0.7 * page_number / total_pages,
                text=f"Extracting page {page_number} of {total_pages}…",
            )
    finally:
        document.close()

    index_pages = analyse_esg(pages, progress_bar)
    return {"pages": pages, "metadata": metadata, "total_pages": total_pages, "index_pages": index_pages}


# =============================================================================
# 6. ESG DETECTION ENGINE (rule-based, keywords checked in context)
# =============================================================================
MIN_WINDOW_SCORE = 3     # minimum score for a sentence window to count as ESG evidence
EDGE_LINES = 3           # number of first/last lines per page treated as header/footer area
MAX_UNIT_CHARS = 350     # long table-like runs of text are cut into pieces of this size

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'(•●▪■])")
PAGE_NUMBER_LINE = re.compile(r"^(?:page\s*)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?$", re.IGNORECASE)
INDEX_HEADING = re.compile(
    r"\b(?:table of contents|contents|content index|gri (?:content )?index|sasb index|brsr index|index)\b",
    re.IGNORECASE,
)

# Normalise characters that often appear in PDFs so keywords match reliably
# (CO₂ -> CO2, typographic hyphens/apostrophes, ligatures, soft hyphens).
NORMALISE_TABLE = {
    ord("₀"): "0", ord("₁"): "1", ord("₂"): "2", ord("₃"): "3", ord("₄"): "4",
    ord("\u00ad"): None, ord("\u2010"): "-", ord("\u2011"): "-", ord("\u2013"): "-",
    ord("\u2014"): "-", ord("\u2019"): "'", ord("\u2018"): "'",
    ord("ﬁ"): "fi", ord("ﬂ"): "fl", ord("ﬀ"): "ff",
}


def normalise_line(line: str) -> str:
    """Lower-case a line and replace digits so '2023 | Page 4' equals '2023 | Page 5'."""
    return " ".join(re.sub(r"\d+", "#", line.lower()).split())


def find_boilerplate_lines(page_texts) -> set:
    """
    Detect running headers/footers: short lines that repeat in the top/bottom lines
    of many pages (e.g. 'Annual Report 2023-24', 'Sustainability Report | 45').
    """
    counts = Counter()
    for text in page_texts:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        edge = lines[:EDGE_LINES] + lines[-EDGE_LINES:]
        counts.update({normalise_line(ln) for ln in edge if len(ln) <= 120})
    threshold = max(3, int(0.2 * len(page_texts)))
    return {line for line, number in counts.items() if line and number >= threshold}


def strip_boilerplate(text: str, boilerplate: set) -> str:
    """Remove repeated headers/footers and bare page numbers from the top/bottom of a page."""
    lines = text.splitlines()
    non_empty = [i for i, ln in enumerate(lines) if ln.strip()]
    edge_positions = set(non_empty[:EDGE_LINES] + non_empty[-EDGE_LINES:])
    kept = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i in edge_positions and (PAGE_NUMBER_LINE.match(stripped) or normalise_line(stripped) in boilerplate):
            continue
        kept.append(line)
    return "\n".join(kept)


def looks_like_index_page(text: str) -> bool:
    """
    Detect contents / GRI-index pages. They list ESG indicator names next to page numbers,
    which would otherwise create false positives.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 10 or not INDEX_HEADING.search(" ".join(lines[:8])):
        return False
    numeric = 0
    for line in lines:
        if re.fullmatch(r"\d{1,3}(?:\s*[-–,]\s*\d{1,3})*", line):
            numeric += 1
        elif re.search(r"\.{3,}\s*\d{1,3}$", line):
            numeric += 1
        elif len(line) < 80 and re.search(r"\s\d{1,3}$", line):
            numeric += 1
    return numeric / len(lines) >= 0.35


def split_into_units(text: str) -> list:
    """Turn page text into sentence-like units (long table-like runs are cut into pieces)."""
    text = text.translate(NORMALISE_TABLE)
    text = re.sub(r"(\w)-\n([a-z])", r"\1\2", text)  # re-join words hyphenated at line end
    flat = re.sub(r"\s+", " ", text).strip()
    units = []
    for sentence in SENTENCE_SPLIT.split(flat):
        while len(sentence) > MAX_UNIT_CHARS:
            cut = sentence.rfind(" ", 0, MAX_UNIT_CHARS)
            cut = cut if cut > 0 else MAX_UNIT_CHARS
            units.append(sentence[:cut])
            sentence = sentence[cut:].strip()
        if sentence:
            units.append(sentence)
    return units


def score_window(rule: EsgRule, window: str):
    """
    Score one text window for one ESG indicator.
        anchor phrase  : 3 points (+1 for each extra distinct anchor, max +2)
        generic terms  : 1 point each (max 3)
        evidence words : +1 (numbers, %, targets, policies ... must accompany a keyword)
    A window scores 0 when it contains an exclusion pattern, or when the rule's
    mandatory context ("require") is missing from the window.
    Returns (score, matched_keywords, position_of_first_match).
    """
    if rule.exclude is not None and rule.exclude.search(window):
        return 0, [], 0
    if rule.require is not None and not rule.require.search(window):
        return 0, [], 0

    anchor_hits, anchor_pos = [], None
    if rule.anchors is not None:
        for match in rule.anchors.finditer(window):
            keyword = " ".join(match.group(0).lower().split())
            if keyword not in anchor_hits:
                anchor_hits.append(keyword)
            if anchor_pos is None:
                anchor_pos = match.start()

    term_hits, term_pos = [], None
    for pattern in rule.terms:
        match = pattern.search(window)
        if match:
            keyword = " ".join(match.group(0).lower().split())
            if keyword not in term_hits and keyword not in anchor_hits:
                term_hits.append(keyword)
            term_pos = match.start() if term_pos is None else min(term_pos, match.start())

    score = 0
    if anchor_hits:
        score += 3 + min(len(anchor_hits) - 1, 2)
    score += min(len(term_hits), 3)
    if (anchor_hits or term_hits) and EVIDENCE_PATTERN.search(window):
        score += 1

    position = anchor_pos if anchor_pos is not None else (term_pos or 0)
    return score, anchor_hits + term_hits, position


def make_snippet(window: str, position: int, width: int = 260) -> str:
    """Cut a short, readable supporting snippet around the first keyword match."""
    start = max(0, position - 100)
    if start > 0:
        space = window.find(" ", start, position)
        if space != -1:
            start = space + 1
    end = min(len(window), start + width)
    if end < len(window):
        space = window.rfind(" ", position, end)
        if space != -1:
            end = space
    snippet = window[start:end].strip()
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(window) else "")


def confidence_label(best_score: int, supporting_windows: int) -> str:
    """Translate the evidence strength into High / Medium / Low."""
    if best_score >= 6 or supporting_windows >= 3:
        return "High"
    if best_score >= 4 or supporting_windows >= 2:
        return "Medium"
    return "Low"


def detect_esg_indicators(clean_text: str) -> list:
    """Detect ESG indicators on one page. One page can return several indicators."""
    units = split_into_units(clean_text)
    if not units:
        return []
    page_flat = " ".join(units)
    # Each window = a sentence plus the next one, so context is checked across sentence breaks.
    windows = [
        unit if i + 1 >= len(units) else f"{unit} {units[i + 1]}"
        for i, unit in enumerate(units)
    ]

    findings = []
    for rule in ESG_RULES:
        # Cheap page-level pre-filters: mandatory context must exist somewhere on the page, and the
        # page needs at least one anchor or two generic terms.
        if rule.require is not None and rule.require.search(page_flat) is None:
            continue
        has_anchor = rule.anchors is not None and rule.anchors.search(page_flat) is not None
        if not has_anchor and sum(1 for t in rule.terms if t.search(page_flat)) < 2:
            continue

        best, supporting, last_counted = None, 0, -10
        for index, window in enumerate(windows):
            score, keywords, position = score_window(rule, window)
            if score < MIN_WINDOW_SCORE:
                continue
            if index - last_counted > 1:  # overlapping windows count as one piece of evidence
                supporting += 1
            last_counted = index
            if best is None or score > best["score"]:
                best = {"score": score, "keywords": keywords, "snippet": make_snippet(window, position)}

        if best:
            findings.append({
                "category": rule.category,
                "indicator": rule.indicator,
                "snippet": best["snippet"],
                "keywords": best["keywords"],
                "score": best["score"],
                "confidence": confidence_label(best["score"], supporting),
            })
    return findings


def analyse_esg(pages, progress_bar) -> list:
    """Run ESG detection on every page with text. Returns the skipped contents/index page numbers."""
    boilerplate = find_boilerplate_lines([p["text"] for p in pages])
    index_pages = []
    total = len(pages)
    for position, page in enumerate(pages, start=1):
        if page["has_text"]:
            if looks_like_index_page(page["text"]):
                index_pages.append(page["number"])
            else:
                page["esg"] = detect_esg_indicators(strip_boilerplate(page["text"], boilerplate))
        progress_bar.progress(
            0.7 + 0.3 * position / total,
            text=f"Detecting ESG indicators… page {position} of {total}",
        )
    return index_pages


# =============================================================================
# 7. DATA BUILDERS (tables, exports, labels)
# =============================================================================
FINDING_COLUMNS = [
    "ESG Category", "ESG Indicator", "Page Number", "Supporting Snippet",
    "Keywords Matched", "Confidence", "Character Count", "Word Count", "Extraction Status",
]


def visible_page_findings(page, min_confidence: str) -> list:
    """ESG findings of one page that meet the minimum confidence level."""
    rank = CONFIDENCE_RANK[min_confidence]
    return [f for f in page["esg"] if CONFIDENCE_RANK[f["confidence"]] >= rank]


def build_findings_df(pages, min_confidence: str) -> pd.DataFrame:
    """One row per (page, ESG indicator). Only pages with detected ESG information appear."""
    rows = []
    for page in pages:
        for finding in visible_page_findings(page, min_confidence):
            rows.append({
                "ESG Category": finding["category"],
                "ESG Indicator": finding["indicator"],
                "Page Number": page["number"],
                "Supporting Snippet": finding["snippet"],
                "Keywords Matched": ", ".join(finding["keywords"][:6]),
                "Confidence": finding["confidence"],
                "Character Count": page["chars"],
                "Word Count": page["words"],
                "Extraction Status": page["status"],
            })
    df = pd.DataFrame(rows, columns=FINDING_COLUMNS)
    if not df.empty:
        df["_order"] = df["ESG Indicator"].map(INDICATOR_ORDER)
        df = df.sort_values(["_order", "Page Number"]).drop(columns="_order").reset_index(drop=True)
    return df


def build_indicators_by_page(findings_df: pd.DataFrame) -> dict:
    """{page_number: [indicator, ...]} in taxonomy order, used for labels and exports."""
    indicators = {}
    for row in findings_df.itertuples(index=False):
        indicators.setdefault(row[2], []).append(row[1])  # columns 1 and 2: indicator, page number
    return {
        page: sorted(set(names), key=lambda name: INDICATOR_ORDER[name])
        for page, names in indicators.items()
    }


def build_summary_df(pages, indicators_by_page) -> pd.DataFrame:
    """Page-wise extraction summary (all pages, original PDF page numbers)."""
    return pd.DataFrame({
        "Page Number": [p["number"] for p in pages],
        "ESG Indicators Detected": ["; ".join(indicators_by_page.get(p["number"], [])) or NO_INDICATORS for p in pages],
        "Character Count": [p["chars"] for p in pages],
        "Word Count": [p["words"] for p in pages],
        "Status": [p["status"] for p in pages],
    })


def build_text_export(pages, file_name, indicators_by_page) -> str:
    """Complete extracted text with clear page separators (ESG indicators shown where detected)."""
    parts = [f"ESG Analyzer - Extracted Text\nSource file: {file_name}\nTotal pages: {len(pages)}"]
    for p in pages:
        header = f"--- PAGE {p['number']}"
        indicators = indicators_by_page.get(p["number"])
        if indicators:
            header += " | ESG: " + "; ".join(indicators)
        parts.append(f"{header} ---\n{p['text']}")
    return "\n\n".join(parts)


def overall_status(pages):
    """Return (label, caption, tone) describing the extraction outcome."""
    empty = sum(1 for p in pages if not p["has_text"])
    if empty == 0:
        return "Complete", "All pages contain text", ""
    if empty == len(pages):
        return "OCR Needed", "No selectable text found", "danger"
    return "Partial", f"{empty} page(s) without text", "warn"


def page_option_label(page, indicators_by_page) -> str:
    """Label used in page selectors: page number plus detected ESG indicators (if any)."""
    indicators = indicators_by_page.get(page["number"])
    if not indicators:
        return f"Page {page['number']}"
    label = ", ".join(indicators)
    if len(label) > 70:
        label = label[:67] + "…"
    return f"Page {page['number']} — {label}"


def indicator_chips(indicators) -> str:
    """Coloured indicator chips (colour = ESG category)."""
    chips = "".join(
        f'<span class="chip chip-{CATEGORY_CLASS[INDICATOR_CATEGORY[t]]}">{esc(t)}</span>' for t in indicators
    )
    return html_block(f"<div>{chips}</div>")


# =============================================================================
# 8. KEYWORD SEARCH AND HIGHLIGHT HELPERS
# =============================================================================
def build_pattern(term: str, case_sensitive: bool):
    """Compile a search pattern; whitespace in the term matches any whitespace/line break."""
    words = term.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    return re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)


def build_keyword_pattern(keywords):
    """Compile one pattern that highlights several detected ESG keywords (whole words only)."""
    unique = sorted({k.strip() for k in keywords if k.strip()}, key=len, reverse=True)
    if not unique:
        return None
    parts = [r"\s+".join(re.escape(w) for w in k.split()) for k in unique]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)


def highlight_html(text: str, pattern) -> str:
    """Return safe HTML for the text with matches of `pattern` wrapped in <mark>."""
    if pattern is None:
        return to_html_text(text)
    out, last = [], 0
    for match in pattern.finditer(text):
        out.append(esc(text[last:match.start()]))
        out.append(f"<mark>{esc(match.group(0))}</mark>")
        last = match.end()
    out.append(esc(text[last:]))
    return "".join(out).replace("\r", "").replace("\n", "<br>")


def search_document(pages, term: str, case_sensitive: bool) -> pd.DataFrame:
    """Search all pages and return one row per matching page."""
    pattern = build_pattern(term, case_sensitive)
    rows = []
    if pattern is None:
        return pd.DataFrame(rows)
    for p in pages:
        matches = list(pattern.finditer(p["text"]))
        if not matches:
            continue
        first = matches[0]
        start, end = max(0, first.start() - 70), min(len(p["text"]), first.end() + 70)
        snippet = " ".join(p["text"][start:end].split())
        rows.append({
            "Page Number": p["number"],
            "Matches": len(matches),
            "Context Snippet": ("…" if start > 0 else "") + snippet + ("…" if end < len(p["text"]) else ""),
        })
    return pd.DataFrame(rows)


def render_text_viewer(text: str, pattern=None):
    st.markdown(
        f'<div class="text-viewer">{highlight_html(text, pattern)}</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# 9. SIDEBAR
# =============================================================================
def render_sidebar(file_name, status_label, status_tone, total_pages, esg_pages):
    with st.sidebar:
        st.markdown(html_block(
            '<div class="sb-brand"><div class="sb-logo">🌱</div><div>'
            '<div class="sb-title">ESG Analyzer</div>'
            '<div class="sb-sub">Corporate Report Processing System</div></div></div>'
        ), unsafe_allow_html=True)

        st.markdown('<div class="sb-section">Current document</div>', unsafe_allow_html=True)
        if file_name:
            pill = {"": "pill-ok", "warn": "pill-warn", "danger": "pill-bad"}.get(status_tone, "pill-ok")
            st.markdown(html_block(
                f'<div class="sb-card"><b>{esc(file_name)}</b><br>{total_pages} pages · '
                f'{esc(esg_pages)} with ESG content<br>'
                f'<span class="pill {pill}">{esc(status_label)}</span></div>'
            ), unsafe_allow_html=True)
        else:
            st.markdown('<div class="sb-card">No document loaded yet.</div>', unsafe_allow_html=True)

        st.markdown('<div class="sb-section">Workflow</div>', unsafe_allow_html=True)
        steps = ["Upload a PDF report", "Automatic text extraction", "Rule-based ESG indicator detection",
                 "Browse, search &amp; download"]
        st.markdown(
            "".join(f'<div class="sb-step"><div class="sb-num">{i}</div><div>{s}</div></div>'
                    for i, s in enumerate(steps, 1)),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sb-section">About this module</div>', unsafe_allow_html=True)
        st.markdown(html_block(
            '<div class="sb-card"><b>Module 1 · PDF Processing</b><br>'
            'Text extraction plus keyword-based detection of 25 ESG indicators '
            '(BRSR, GRI and ESRS terminology). '
            'AI-based ESG analysis will be added in a later module.</div>'
        ), unsafe_allow_html=True)


# =============================================================================
# 10. MAIN APPLICATION - HEADER, UPLOAD AND PROCESSING
# =============================================================================
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---- Hero header ------------------------------------------------------------
st.markdown(html_block(
    '<div class="hero"><span class="hero-badge">MODULE 1 · PDF PROCESSING &amp; ESG INDICATOR DETECTION</span>'
    '<h1>🌱 ESG Analyzer</h1>'
    '<p>Upload a corporate annual or sustainability report to extract its text, find the pages '
    'that report 25 Environmental, Social and Governance indicators, and export the results.</p></div>'
), unsafe_allow_html=True)

# ---- Upload -------------------------------------------------------------------
section_title("Upload Report", "Drag and drop a text-based PDF report, or browse your files.")
uploaded_file = st.file_uploader(
    "Upload your corporate PDF report",
    type=["pdf"],
    label_visibility="collapsed",
)

# ---- Process the PDF once per unique file (results kept in session state) -----
if "viewer_idx" not in st.session_state:
    st.session_state["viewer_idx"] = 0

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_key = hashlib.sha256(file_bytes).hexdigest()

    if st.session_state.get("file_key") != file_key:
        progress_holder = st.empty()
        progress_bar = progress_holder.progress(0.0, text="Opening PDF…")
        try:
            st.session_state["result"] = extract_document(file_bytes, progress_bar)
            st.session_state["error"] = None
        except PDFProcessingError as exc:
            st.session_state["result"] = None
            st.session_state["error"] = str(exc)
        except Exception as exc:  # any unexpected failure
            st.session_state["result"] = None
            st.session_state["error"] = f"Unexpected error while processing the PDF: {exc}"
        st.session_state["file_key"] = file_key
        st.session_state["viewer_idx"] = 0
        progress_holder.empty()

    result = st.session_state.get("result")
    error_message = st.session_state.get("error")
else:
    result, error_message = None, None

# ---- ESG results for the current confidence setting (the widget lives in the ESG tab) --
if result:
    min_confidence = st.session_state.get("esg_min_conf", DEFAULT_CONFIDENCE)
    if min_confidence not in CONFIDENCE_RANK:
        min_confidence = DEFAULT_CONFIDENCE
    findings_df = build_findings_df(result["pages"], min_confidence)
    indicators_by_page = build_indicators_by_page(findings_df)
else:
    min_confidence = DEFAULT_CONFIDENCE
    findings_df = pd.DataFrame(columns=FINDING_COLUMNS)
    indicators_by_page = {}

# ---- Sidebar (rendered after processing so it can show the file status) -------
if result:
    _label, _caption, _tone = overall_status(result["pages"])
    render_sidebar(uploaded_file.name, _label, _tone, result["total_pages"], len(indicators_by_page))
else:
    render_sidebar(None, "", "", 0, 0)

# ---- Landing page when no file --------------------------------------------------
if uploaded_file is None:
    section_title("How it works", "Three simple steps from PDF to ESG-relevant pages.")
    c1, c2, c3 = st.columns(3)
    cards = [
        ("📤", "1. Upload", "Add an annual, sustainability, BRSR or ESG report in PDF format."),
        ("🌿", "2. Extract &amp; detect",
         "Text and metadata are extracted, then pages reporting any of the 25 Environmental, Social and "
         "Governance indicators are identified."),
        ("📥", "3. Review &amp; export", "Browse ESG indicators, search keywords, and download the TXT and CSV outputs."),
    ]
    for col, (icon, title, text) in zip((c1, c2, c3), cards):
        col.markdown(
            f'<div class="step-card"><div class="icon">{icon}</div><h4>{title}</h4><p>{text}</p></div>',
            unsafe_allow_html=True,
        )
    st.info("ℹ️ Only PDFs with selectable text are supported. Scanned PDFs need OCR, which is not part of this module.")
    st.stop()

# ---- Error page ------------------------------------------------------------------
if error_message:
    st.error(f"❌ Unable to process this PDF. {error_message}")
    st.stop()

# =============================================================================
# 11. DASHBOARD
# =============================================================================
pages = result["pages"]
metadata = result["metadata"]
total_pages = result["total_pages"]
total_chars = sum(p["chars"] for p in pages)
empty_pages = [p["number"] for p in pages if not p["has_text"]]
status_label, status_caption, status_tone = overall_status(pages)
summary_df = build_summary_df(pages, indicators_by_page)
file_size_text = format_file_size(len(uploaded_file.getvalue()))
page_lookup = {p["number"]: p for p in pages}

st.success("✅ PDF uploaded and processed successfully!")

# ---- Metric cards ---------------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
m1.markdown(metric_card("Total Pages", f"{total_pages:,}", "Original PDF pages"), unsafe_allow_html=True)
m2.markdown(metric_card("Extracted Characters", f"{total_chars:,}", "Across all pages"), unsafe_allow_html=True)
m3.markdown(metric_card("File Size", file_size_text, uploaded_file.name), unsafe_allow_html=True)
m4.markdown(metric_card("Extraction Status", status_label, status_caption, status_tone), unsafe_allow_html=True)

# ---- Scanned / OCR warnings ------------------------------------------------------
if empty_pages:
    page_list = format_page_ranges(empty_pages)
    if len(empty_pages) == total_pages:
        st.error(
            "🖨️ **This looks like a fully scanned PDF.** No selectable text was found on any page. "
            "OCR (optical character recognition) is required before the text can be extracted."
        )
    else:
        st.warning(
            f"⚠️ **{len(empty_pages)} of {total_pages} pages contain no selectable text** "
            f"(pages {page_list}). They may be scanned images and would require OCR."
        )

# ---- Document information ---------------------------------------------------------
section_title("Document Information", "File details and metadata embedded in the PDF.")
left, right = st.columns(2)
left.markdown(info_card("📁 File details", [
    ("File name", uploaded_file.name),
    ("File size", file_size_text),
    ("Total pages", f"{total_pages:,}"),
    ("Pages with text", f"{total_pages - len(empty_pages):,}"),
    ("Pages without text", f"{len(empty_pages):,}"),
    ("Pages with ESG content", f"{len(indicators_by_page):,}"),
]), unsafe_allow_html=True)
right.markdown(info_card("🏷️ PDF metadata", [
    ("Document title", clean_meta(metadata.get("title"))),
    ("Author", clean_meta(metadata.get("author"))),
    ("Subject", clean_meta(metadata.get("subject"))),
    ("Keywords", clean_meta(metadata.get("keywords"))),
    ("Created with", clean_meta(metadata.get("creator"))),
    ("Created on", format_pdf_date(metadata.get("creationDate"))),
]), unsafe_allow_html=True)

# ---- Tabs -------------------------------------------------------------------------
section_title("Report Explorer", "Review detected ESG indicators, browse pages, search and export.")
tab_esg, tab_viewer, tab_search, tab_summary, tab_downloads = st.tabs(
    ["🌿 ESG Indicators", "📄 Page Viewer", "🔍 Keyword Search", "📊 Page Summary", "⬇️ Downloads"]
)

# ---- Tab 1: ESG indicators (only pages with relevant ESG information) ----------------
with tab_esg:
    st.caption(
        "Rule-based keyword detection of 25 ESG indicators (BRSR, GRI and ESRS terminology): an indicator is "
        "reported only when its keywords appear in a meaningful context (specific disclosure phrases, or several "
        "related terms together with required context words, figures, targets or policies). "
        "Repeated headers/footers and contents pages are ignored. No AI is used."
    )

    f1, f2, f3 = st.columns([1.2, 1.4, 2])
    f1.select_slider("Minimum confidence", options=CONFIDENCE_LEVELS,
                     value=DEFAULT_CONFIDENCE, key="esg_min_conf")
    category_filter = f2.multiselect("ESG category", CATEGORY_ORDER, default=CATEGORY_ORDER, key="esg_cat_filter")
    available_indicators = [t for t in INDICATOR_ORDER if t in set(findings_df["ESG Indicator"])]
    indicator_filter = f3.multiselect("ESG indicator (leave empty for all)", available_indicators)

    detected_total = sum(len(p["esg"]) for p in pages)
    hidden_count = detected_total - len(findings_df)

    if result["index_pages"]:
        st.caption(
            f"ℹ️ {len(result['index_pages'])} contents/index page(s) were skipped to avoid false positives "
            f"(pages {format_page_ranges(result['index_pages'])})."
        )

    if findings_df.empty:
        if len(empty_pages) == total_pages:
            st.warning("No ESG information could be detected because the PDF has no selectable text. OCR is required first.")
        elif hidden_count > 0:
            st.info(
                f"No ESG indicators were detected at **{min_confidence}** confidence or higher. "
                f"{hidden_count} lower-confidence detection(s) are hidden; "
                "lower the minimum confidence above to see them."
            )
        else:
            st.info(
                "None of the 25 monitored ESG indicators was detected in this document. "
                "The report may not disclose them, or the relevant content may be inside scanned images."
            )
    else:
        # ---- Category summary cards
        cards = st.columns(5)
        cards[0].markdown(metric_card("ESG-Relevant Pages", f"{len(indicators_by_page):,}", f"of {total_pages:,} pages"),
                          unsafe_allow_html=True)
        cards[1].markdown(metric_card("Indicators Identified", f"{findings_df['ESG Indicator'].nunique():,}",
                                      f"of {len(ESG_RULES)} monitored indicators"), unsafe_allow_html=True)
        for column, category in zip(cards[2:], CATEGORY_ORDER):
            subset = findings_df[findings_df["ESG Category"] == category]
            monitored = sum(1 for r in ESG_RULES if r.category == category)
            column.markdown(metric_card(category, f"{subset['Page Number'].nunique():,}",
                                        f"pages · {subset['ESG Indicator'].nunique()} of {monitored} indicators"),
                            unsafe_allow_html=True)
        if hidden_count > 0:
            st.caption(f"{hidden_count} lower-confidence detection(s) are hidden at the current setting.")

        # ---- Filtered findings table
        view_df = findings_df[findings_df["ESG Category"].isin(category_filter)]
        if indicator_filter:
            view_df = view_df[view_df["ESG Indicator"].isin(indicator_filter)]

        st.markdown("**Detected ESG information by indicator**")
        if view_df.empty:
            st.warning("No results match the selected filters.")
        else:
            config = None
            if hasattr(st, "column_config"):
                config = {
                    "Supporting Snippet": st.column_config.TextColumn("Supporting Snippet", width="large"),
                    "Page Number": st.column_config.NumberColumn("Page Number", format="%d"),
                }
            show_table(view_df, height=min(560, 60 + 38 * len(view_df)), column_config=config)

            # ---- Indicator coverage chart
            st.markdown("**Pages per ESG indicator**")
            coverage = view_df.groupby("ESG Indicator")["Page Number"].nunique().rename("Pages")
            coverage = coverage.reindex([t for t in INDICATOR_ORDER if t in coverage.index])  # taxonomy order
            try:
                st.bar_chart(coverage, color="#10b981")
            except Exception:
                st.bar_chart(coverage)

            # ---- Page preview with detected keywords highlighted
            st.markdown("**Preview a page with ESG content**")
            chosen = st.selectbox(
                "Page with ESG content",
                sorted(view_df["Page Number"].unique().tolist()),
                format_func=lambda n: page_option_label(page_lookup[n], indicators_by_page),
                label_visibility="collapsed",
            )
            chosen_page = page_lookup[chosen]
            chosen_findings = visible_page_findings(chosen_page, min_confidence)
            st.markdown(indicator_chips([f["indicator"] for f in sorted(chosen_findings, key=lambda f: INDICATOR_ORDER[f["indicator"]])]),
                        unsafe_allow_html=True)
            render_text_viewer(
                chosen_page["text"],
                build_keyword_pattern([k for f in chosen_findings for k in f["keywords"]]),
            )

    with st.expander("📋 The 25 indicators monitored by the rule-based detector"):
        columns = st.columns(3)
        for column, category in zip(columns, CATEGORY_ORDER):
            numbered = [(n, r.indicator) for n, r in enumerate(ESG_RULES, 1) if r.category == category]
            items = "".join(f"<li value='{n}'>{esc(t)}</li>" for n, t in numbered)
            column.markdown(
                html_block(f'<div class="info-card"><h4>{esc(category)} ({len(numbered)})</h4>'
                           f'<ol class="rule-list">{items}</ol></div>'),
                unsafe_allow_html=True,
            )

# ---- Tab 2: Page viewer with navigation ----------------------------------------------
with tab_viewer:
    last_index = total_pages - 1

    def step_page(delta: int):
        """Callback for the Previous / Next buttons."""
        new_value = st.session_state["viewer_idx"] + delta
        st.session_state["viewer_idx"] = min(max(new_value, 0), last_index)

    nav_prev, nav_select, nav_next = st.columns([1, 4, 1])
    nav_prev.button("◀ Previous", on_click=step_page, args=(-1,), key="btn_prev",
                    disabled=st.session_state["viewer_idx"] == 0)
    nav_select.selectbox(
        "Jump to page",
        options=list(range(total_pages)),
        format_func=lambda i: page_option_label(pages[i], indicators_by_page),
        key="viewer_idx",
        label_visibility="collapsed",
    )
    nav_next.button("Next ▶", on_click=step_page, args=(1,), key="btn_next",
                    disabled=st.session_state["viewer_idx"] == last_index)

    current = pages[st.session_state["viewer_idx"]]
    highlight_term = st.text_input(
        "Highlight a keyword on this page (optional)", key="viewer_highlight",
        placeholder="e.g. emissions",
    )

    st.markdown(
        html_block(
            f'<div class="page-badge">Page {current["number"]} of {total_pages} · '
            f'{current["chars"]:,} characters · {current["words"]:,} words · {esc(current["status"])}</div>'
        ),
        unsafe_allow_html=True,
    )
    page_indicators = indicators_by_page.get(current["number"], [])
    if page_indicators:
        st.markdown(indicator_chips(page_indicators), unsafe_allow_html=True)

    if current["has_text"]:
        render_text_viewer(current["text"], build_pattern(highlight_term, False))
        with st.expander("Copy-friendly plain text"):
            st.text_area("Extracted text", current["text"], height=250,
                         key=f"plain_{current['number']}", label_visibility="collapsed")
    elif current["status"] == "Extraction error":
        st.error("An error occurred while extracting this page.")
    else:
        st.warning("No selectable text found on this page. It may contain a scanned image and require OCR.")

# ---- Tab 3: Keyword search across the whole document ------------------------------------
with tab_search:
    s1, s2 = st.columns([4, 1])
    search_term = s1.text_input("Search the entire document", key="search_term",
                                placeholder="Enter a keyword or phrase, e.g. carbon emissions")
    case_sensitive = s2.checkbox("Case sensitive", value=False, key="search_case")
    s2.markdown("&nbsp;", unsafe_allow_html=True)

    if not search_term.strip():
        st.info("Type a keyword or phrase above to find every page where it appears.")
    else:
        results_df = search_document(pages, search_term, case_sensitive)
        if results_df.empty:
            st.warning(f"No matches found for “{search_term}”.")
        else:
            total_matches = int(results_df["Matches"].sum())
            matched_numbers = results_df["Page Number"].tolist()
            r1, r2 = st.columns(2)
            r1.markdown(metric_card("Total Matches", f"{total_matches:,}", f"for “{search_term}”"),
                        unsafe_allow_html=True)
            r2.markdown(metric_card("Pages Matched", f"{len(matched_numbers):,}", f"of {total_pages} pages"),
                        unsafe_allow_html=True)

            st.markdown(f"**Matching page numbers:** {format_page_ranges(matched_numbers)}")
            show_table(results_df, height=min(420, 40 + 36 * len(results_df)))

            st.markdown("**Preview a matching page**")
            chosen_match = st.selectbox(
                "Matching page", matched_numbers,
                format_func=lambda n: page_option_label(page_lookup[n], indicators_by_page),
                label_visibility="collapsed",
            )
            render_text_viewer(page_lookup[chosen_match]["text"], build_pattern(search_term, case_sensitive))

        if empty_pages:
            st.caption(f"Note: {len(empty_pages)} page(s) have no selectable text and cannot be searched.")

# ---- Tab 4: Page-wise summary --------------------------------------------------------------
with tab_summary:
    p1, p2 = st.columns(2)
    only_empty = p1.checkbox("Show only pages without selectable text", value=False)
    only_esg = p2.checkbox("Show only pages with detected ESG indicators", value=False)

    table_df = summary_df
    if only_empty:
        table_df = table_df[table_df["Status"] != "Text extracted"]
    if only_esg:
        table_df = table_df[table_df["ESG Indicators Detected"] != NO_INDICATORS]

    if table_df.empty:
        st.success("No pages match the selected filters.")
    else:
        show_table(table_df, height=480)
    st.caption(
        "All pages are listed with their original PDF page numbers. “ESG Indicators Detected” shows a dash "
        "when none of the 25 monitored indicators was found on the page."
    )

# ---- Tab 5: Downloads ------------------------------------------------------------------------
with tab_downloads:
    safe_stem = re.sub(r"[^\w\-]+", "_", uploaded_file.name.rsplit(".", 1)[0]).strip("_") or "report"
    complete_text = build_text_export(pages, uploaded_file.name, indicators_by_page)

    st.markdown(html_block(
        '<div class="dl-card"><h4>📝 Complete extracted text (.txt)</h4>'
        '<p>All pages in one file, separated by page number (ESG indicators are shown where detected).</p></div>'
    ), unsafe_allow_html=True)
    st.download_button(
        label="⬇️ Download Extracted Text (.txt)",
        data=complete_text.encode("utf-8"),
        file_name=f"{safe_stem}_extracted_text.txt",
        mime="text/plain",
        key="download_txt",
    )

    st.markdown(html_block(
        '<div class="dl-card" style="margin-top:1.2rem;"><h4>📊 Page-wise extraction summary (.csv)</h4>'
        '<p>Page number, detected ESG indicators, character and word counts, and extraction status for every page.</p></div>'
    ), unsafe_allow_html=True)
    st.download_button(
        label="⬇️ Download Extraction Summary (.csv)",
        data=summary_df.to_csv(index=False).encode("utf-8-sig"),  # utf-8-sig opens cleanly in Excel
        file_name=f"{safe_stem}_extraction_summary.csv",
        mime="text/csv",
        key="download_csv",
    )

    st.markdown(html_block(
        '<div class="dl-card" style="margin-top:1.2rem;"><h4>🌿 Detected ESG indicators (.csv)</h4>'
        '<p>ESG category, indicator, PDF page number, supporting snippet, matched keywords, confidence, counts and '
        'status (uses the current minimum confidence setting).</p></div>'
    ), unsafe_allow_html=True)
    st.download_button(
        label="⬇️ Download ESG Indicators (.csv)",
        data=findings_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{safe_stem}_esg_indicators.csv",
        mime="text/csv",
        key="download_esg_csv",
        disabled=findings_df.empty,
    )
    if findings_df.empty:
        st.caption("No ESG indicators were detected, so there is nothing to export in this file.")