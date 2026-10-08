import pandas as pd

from src import config
from src.data import get_info


def get_peer_financials(peer_tickers):

    rows = []

    for ticker in peer_tickers:

        try:

            info = get_info(ticker)

            rows.append({
                "Ticker": ticker,
                "Company": info.get("longName"),
                "Price": info.get("currentPrice"),
                "Market_Cap": info.get("marketCap"),
                "EPS": info.get("trailingEps"),
                "PE": info.get("trailingPE"),
                "PB": info.get("priceToBook"),
                "EVS": info.get("enterpriseToRevenue"),
                "ROE": info.get("returnOnEquity"),
                "Profit_Margin": info.get("profitMargins"),
                "Operating_Margin": (
                    info["operatingMargins"] * 100
                    if isinstance(info.get("operatingMargins"), (int, float))
                    else None
                ),
                "Debt_to_Equity": info.get("debtToEquity"),
                "Sector": info.get("sector"),
                "Industry": info.get("industry"),
                "Industry_Key": info.get("industryKey"),
                "Summary": info.get("longBusinessSummary"),
            })

        except Exception:
            continue

    columns = [
        "Ticker", "Company", "Price", "Market_Cap", "EPS", "PE",
        "PB", "EVS", "ROE", "Profit_Margin", "Operating_Margin", "Debt_to_Equity",
        "Sector", "Industry", "Industry_Key", "Summary"
    ]

    data = pd.DataFrame(rows, columns=columns)

    numeric = [
        "Price", "Market_Cap", "EPS", "PE", "PB", "EVS",
        "ROE", "Profit_Margin", "Operating_Margin", "Debt_to_Equity"
    ]

    data[numeric] = data[numeric].apply(
        pd.to_numeric, errors="coerce"
    )

    return data


def clean_peers(peer_data, target_ticker, multiple="PE"):
    """
    Keep peers with valid data for the requested multiple.

    For P/E this keeps the original rule: positive EPS and
    positive P/E.
    """

    data = peer_data.copy()

    if data.empty:
        return data

    # Remove the target company
    data = data[
        data["Ticker"] != target_ticker
    ]

    if multiple == "PE":
        data = data[
            data["EPS"].notna()
            & (data["EPS"] > 0)
        ]

    # Require valid positive multiple
    data = data[
        data[multiple].notna()
        & (data[multiple] > 0)
    ]

    # Require valid market cap
    data = data[
        data["Market_Cap"].notna()
        & (data["Market_Cap"] > 0)
    ]

    return data


def select_comparable_peers(
    peer_data,
    target_ticker,
    number_of_peers=10,
    multiple="PE"
):
    """
    Rank valid peers by business-description similarity when it
    is available, otherwise by market cap.

    Evidence (scripts/evaluate_peers.py, 560 Indian companies):
    same-ownership + similarity peers predict a company's own
    P/E and P/B better than top-by-market-cap peers
    (P/E: 57% -> 53% typical miss; P/B: 77% -> 63%; both
    improvements significant in a paired bootstrap).
    """

    data = clean_peers(
        peer_data,
        target_ticker,
        multiple=multiple
    )

    if data.empty:
        return data

    if "Similarity" in data.columns and data["Similarity"].notna().sum() >= 3:
        ranking = ["Similarity", "Market_Cap"]
    else:
        ranking = ["Market_Cap"]

    data = data.sort_values(ranking, ascending=False)

    return data.head(
        number_of_peers
    )


def calculate_peer_median_pe(peer_data):

    if peer_data.empty:
        return None

    return peer_data["PE"].median()


def summarize_multiple(values):
    """
    Median and spread of a peer multiple.

    With enough peers the interquartile range is used: it is a
    defensible "typical peer" band that ignores outliers.
    With few peers, min/max is used and flagged.
    """

    values = pd.Series(values, dtype="float64").dropna()

    values = values[values > 0]

    count = len(values)

    if count == 0:
        return None

    if count >= config.MIN_PEERS_FOR_QUARTILES:
        low = values.quantile(0.25)
        high = values.quantile(0.75)
        spread_basis = "interquartile range"
    else:
        low = values.min()
        high = values.max()
        spread_basis = "min-max (too few peers for quartiles)"

    return {
        "median": float(values.median()),
        "low": float(low),
        "high": float(high),
        "count": count,
        "spread_basis": spread_basis,
    }


def build_multiple_analysis(
    peer_data,
    target_ticker,
    multiple,
    number_of_peers=config.PEER_COUNT
):

    selected = select_comparable_peers(
        peer_data,
        target_ticker,
        number_of_peers=number_of_peers,
        multiple=multiple
    )

    summary = summarize_multiple(
        selected[multiple] if not selected.empty else []
    )

    return {
        "selected_peers": selected,
        "summary": summary,
        "peer_count": len(selected),
    }


MIN_SAME_OWNERSHIP_PEERS = 5

# Peers smaller than this fraction of the target's market cap are
# excluded (if enough remain): micro-caps carry noisy multiples.
# Evidence (scripts/evaluate_peers.py): with the floor, peer median
# P/E predicts a company's own P/E better (typical miss 53% -> 50%);
# P/B accuracy unchanged.
SIZE_FLOOR = 0.20
MIN_PEERS_AFTER_FLOOR = 5


def apply_size_floor(peer_data, target_market_cap):

    if (
        peer_data.empty
        or not target_market_cap
        or "Market_Cap" not in peer_data.columns
    ):
        return peer_data, ""

    floor = SIZE_FLOOR * target_market_cap

    big_enough = peer_data[peer_data["Market_Cap"] >= floor]

    if len(big_enough) >= MIN_PEERS_AFTER_FLOOR:
        excluded = len(peer_data) - len(big_enough)
        return big_enough, (
            f" {excluded} candidates below {SIZE_FLOOR:.0%} of the "
            "company's market cap excluded."
        )

    return peer_data, " Too few larger peers: no size floor applied."


def apply_ownership_filter(peer_data, target_ticker, target_ownership):
    """
    Prefer peers with the same ownership type (PSU vs private),
    because PSUs trade at structurally different multiples.
    Falls back to the full set when too few same-ownership
    peers have valid earnings multiples.
    """

    if (
        peer_data.empty
        or "Ownership" not in peer_data.columns
        or target_ownership not in ("PSU", "Private")
    ):
        return peer_data, "Ownership not used (unknown)."

    same = peer_data[peer_data["Ownership"] == target_ownership]

    valid = clean_peers(same, target_ticker, multiple="PE")

    excluded = len(peer_data) - len(same)

    if len(valid) >= MIN_SAME_OWNERSHIP_PEERS:
        return same, (
            f"Compared with {target_ownership} peers only "
            f"({excluded} other-ownership candidates excluded)."
        )

    return peer_data, (
        f"Mixed ownership: only {len(valid)} valid {target_ownership} "
        "peers, so all candidates were kept."
    )


def add_similarity(peer_data, target_summary):
    """
    Cosine similarity between each peer's business description
    and the target's. Returns (data, note); never raises.
    """

    if peer_data.empty or not isinstance(target_summary, str):
        return peer_data, "Peers ranked by market cap (no description)."

    try:
        from src.embeddings import similarity_to

        similarity = similarity_to(target_summary, peer_data["Summary"].tolist())

    except Exception as error:
        return peer_data, (
            f"Peers ranked by market cap (embeddings unavailable: {error})."
        )

    return (
        peer_data.assign(Similarity=similarity),
        "Peers ranked by business-description similarity.",
    )


def build_peer_analysis(
    peer_data,
    target_ticker,
    number_of_peers=10,
    target_ownership=None,
    target_summary=None,
    target_market_cap=None
):

    peer_data, ownership_note = apply_ownership_filter(
        peer_data, target_ticker, target_ownership
    )

    peer_data, size_note = apply_size_floor(peer_data, target_market_cap)

    ownership_note += size_note

    peer_data, ranking_note = add_similarity(peer_data, target_summary)

    selected_peers = select_comparable_peers(
        peer_data=peer_data,
        target_ticker=target_ticker,
        number_of_peers=number_of_peers
    )

    median_pe = calculate_peer_median_pe(
        selected_peers
    )

    multiples = {
        multiple: build_multiple_analysis(
            peer_data,
            target_ticker,
            multiple,
            number_of_peers
        )
        for multiple in ("PE", "PB", "EVS")
    }

    # Peer ROE (used for the ROE-adjusted P/B).
    roe_values = pd.Series(dtype="float64")

    pb_peers = multiples["PB"]["selected_peers"]

    if not pb_peers.empty:
        roe_values = pb_peers["ROE"].dropna()
        roe_values = roe_values[roe_values > 0]

    return {
        "selected_peers": selected_peers,
        "median_pe": median_pe,
        "peer_count": len(selected_peers),
        "multiples": multiples,
        "ownership_note": ownership_note,
        "ranking_note": ranking_note,
        "mixed_ownership": ownership_note.startswith("Mixed"),
        "median_peer_roe": (
            float(roe_values.median()) * 100
            if not roe_values.empty
            else None
        ),
    }
