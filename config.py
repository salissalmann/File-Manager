"""Configuration for the file-to-ledger matching engine."""

from decimal import Decimal

# --- Scoring Weights ---
AMOUNT_EXACT_WEIGHT = 50
AMOUNT_NEAR_WEIGHT = 40
AMOUNT_SUM_WEIGHT = 35       # partial payment: ledger amounts sum to file amount
CA_MATCH_WEIGHT = 30
VENDOR_STRONG_WEIGHT = 20
VENDOR_PARTIAL_WEIGHT = 10
INVOICE_MATCH_WEIGHT = 5     # invoice number tie-breaker bonus

# --- Penalties ---
MULTI_AMOUNT_PENALTY = 5     # deducted when file has >1 amount (ambiguity)

# --- Thresholds ---
VENDOR_STRONG_THRESHOLD = 85  # fuzzy ratio >= this = strong vendor match
VENDOR_PARTIAL_THRESHOLD = 65  # fuzzy ratio >= this = partial vendor match
VENDOR_VETO_THRESHOLD = 45  # fuzzy ratio < this AND file has vendor tokens = veto

# --- Amount Tolerance ---
AMOUNT_ABS_TOLERANCE = Decimal("1.00")  # $1.00 absolute tolerance
AMOUNT_REL_TOLERANCE = Decimal("0.005")  # 0.5% relative tolerance

# --- Status Classification ---
STRONG_THRESHOLD = 80  # score >= this = Strong
GOOD_THRESHOLD = 50  # score >= this = Good
# Below GOOD_THRESHOLD with a match = Review
# No match at all = No Match

# --- Default file base path for clickable links ---
DEFAULT_BASE_PATH = ""  # set via --base-path CLI arg

# --- Common keywords to strip from vendor extraction ---
NOISE_WORDS = {
    "invoice", "inv", "partial", "project", "misc", "materials",
    "framing", "part1", "part2", "second", "reprint", "wrongca",
    "wrongamount", "pdf", "milford", "by",
}
