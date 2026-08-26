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

NAKED_SHORTS = False
MARGIN_NAKED = False
ALLOW_LIVE = False
AUTO_TRADE = False
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
