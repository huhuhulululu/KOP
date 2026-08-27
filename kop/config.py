from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LEDGER_PATH = DATA_DIR / "kop.sqlite"
RESEARCH_DIR = DATA_DIR / "research"
CATALOG_RESEARCH = ROOT / "catalog" / "research"

# --- frozen playbook: nvda_earnings_defined_short_vol ---
PLAYBOOK = "nvda_earnings_defined_short_vol"
SYMBOL = "NVDA"
WATCHLIST_OBSERVE_ONLY = ("TSLA", "NVDA", "AAPL", "MSFT", "AMZN")

ENTRY_DAYS_BEFORE = (2, 5)
DEFAULT_ENTRY_DAYS_BEFORE = 3
EXIT_TRADING_DAYS_AFTER = 1
CREDIT_TAKE_FRACTION = 0.50

STRUCTURE = "short_iron_condor"
WING_WIDTH_USD = 5.0
CONTRACTS = 1
MAX_LOSS_USD = 500.0
MAX_LEG_SPREAD_USD = 0.40
SLIPPAGE_PER_LEG_USD = 0.05
FEE_PER_CONTRACT = 0.65
MULTIPLIER = 100

# CBOE iv30 vs trailing 1y high/low. Not a 252-day percentile.
# When the ledger holds >= IV_PERCENTILE_MIN_SAMPLES daily iv30 prints,
# the live gate switches to true percentile. Threshold stays 50.
IV_RANK_MIN = 50.0
IV_PERCENTILE_MIN_SAMPLES = 60

# Snapshot gates. Fail-closed. Changing a number = new playbook name.
SHORT_VOL_IMPLIED_OVER_HIST_MIN = 1.2
LONG_VOL_IMPLIED_OVER_HIST_MAX = 1.0
VRP_IV30_OVER_HV20_MIN = 1.0
TERM_SLOPE_VOL_MIN = 15.0
ATM_STRADDLE_SPREAD_MAX = 0.08
PATH_HIT_RATE_MIN = 0.50
PATH_HIT_MIN_EVENTS = 4
IC_CREDIT_OVER_WIDTH_MIN = 0.20
ATM_OI_MIN = 500
HV_FAST_WINDOW = 20
HV_SLOW_WINDOW = 60
FRONT_DTE_MAX = 10
BACK_DTE_MIN = 21
BACK_DTE_MAX = 45
RR_DELTA_TARGET = 0.25
RR_DELTA_TOLERANCE = 0.10

NAKED_SHORTS = False
MARGIN_NAKED = False
ALLOW_LIVE = False
AUTO_TRADE = False
# Book a CBOE bid/ask paper fill when every short-vol gate is open.
# This is not a broker order. ALLOW_LIVE / AUTO_TRADE stay off.
PAPER_FILLS = True
MAX_OPEN_POSITIONS = 1
MONTHLY_INCOME_TARGET_USD = 500.0
EVENTS_PER_YEAR = 4
MIN_COUNTABLE_TAPE_FOR_LIVE = 8
# Human fills are optional overlays. Public recipes + path replay are the tape.
REQUIRE_HUMAN_TAPE = False
MIN_TAPE_SAMPLES_FOR_LOOP = 0
MIN_PUBLIC_REPLAY_EVENTS = 4
CATALOG_PUBLIC = ROOT / "catalog" / "public"

CONTRAST_VARIANTS = (
    "short_iron_condor",
    "short_iron_fly",
    "put_credit_spread",
    "call_credit_spread",
    "reverse_iron_condor",
    "long_straddle",
    "long_strangle",
    "long_call",
    "long_put",
    "calendar_short_front",
    "do_nothing",
)

HTTP_USER_AGENT = "kop-paper/0.1 (+listed-options-research; not a broker)"
