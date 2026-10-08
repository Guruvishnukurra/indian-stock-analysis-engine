"""
Ownership classification: public-sector (PSU) vs private.

Indian PSUs (government-controlled) trade at structurally lower
multiples than private peers, so mixing them in one peer median
biases valuation. Ownership comes from NSE's official PSU index
constituent lists, not from a hand-maintained list of companies.

Coverage: companies in NIFTY PSU Bank, NIFTY PSE and NIFTY CPSE.
Smaller PSUs outside these indices are not detected.
"""

import io

import pandas as pd
import requests

from src.cache import DAY, cached


NSE_PSU_LISTS = [
    "ind_niftypsubanklist",
    "ind_niftypselist",
    "ind_niftycpselist",
]

URL = "https://www.niftyindices.com/IndexConstituent/{name}.csv"


@cached("ownership", 7 * DAY)
def get_psu_symbols():
    """Set of NSE symbols that appear in an NSE PSU index."""

    symbols = set()

    for name in NSE_PSU_LISTS:

        response = requests.get(
            URL.format(name=name),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )

        response.raise_for_status()

        data = pd.read_csv(io.StringIO(response.text))

        symbols.update(data["Symbol"].astype(str).str.upper())

    return sorted(symbols)


def base_symbol(ticker):
    return str(ticker).rsplit(".", 1)[0].upper()


def ownership_lookup():
    """
    Returns (function ticker -> "PSU"/"Private", available flag).
    If the NSE lists cannot be fetched, ownership is unknown.
    """

    try:
        psu = set(get_psu_symbols())
    except Exception:
        psu = set()

    if not psu:
        return (lambda ticker: "Unknown"), False

    def classify(ticker):
        return "PSU" if base_symbol(ticker) in psu else "Private"

    return classify, True
