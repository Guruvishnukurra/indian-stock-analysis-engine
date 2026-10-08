import numpy as np
import pandas as pd

from src.periods import build_ttm, fy_label, normalized_eps


def quarterly(dates, revenue, operating, net, normalized=None):
    data = pd.DataFrame({
        "Revenue": revenue,
        "Operating_Income": operating,
        "Net_Income": net,
        "Normalized_Income": normalized if normalized is not None else net,
        "Unusual_Items": 0.0,
    }, index=pd.to_datetime(dates))
    return data


def test_ttm_requires_consecutive_quarters():
    gap = quarterly(
        ["2025-03-31", "2025-06-30", "2025-12-31", "2026-03-31"],   # Sep missing
        [100] * 4, [10] * 4, [8] * 4,
    )
    assert not build_ttm(gap)["available"]

    complete = quarterly(
        ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"],
        [100, 110, 120, 130], [-10, -5, 0, 5], [-12, -6, -1, 4],
    )
    ttm = build_ttm(complete)

    assert ttm["available"]
    assert ttm["Revenue"] == 460
    assert ttm["Operating_Margin"] == (-10 / 460) * 100
    assert ttm["label"] == "TTM to 31 Mar 2026"


def test_one_offs_removed_from_eps_within_trailing_window():
    data = quarterly(
        ["2025-06-30", "2025-12-31", "2026-03-31", "2026-06-30"],
        [100] * 4, [20] * 4,
        net=[10, 7, 10, 9],
        normalized=[10, 10, 10, 10],      # charges of 3 and 1 after tax
    )
    data["Unusual_Items"] = [0, -4, 0, -1.3]

    # 2025-06-30 is exactly 365 days before the latest quarter: excluded.
    eps, note = normalized_eps(trailing_eps=3.6, quarterly_data=data, shares=10)

    assert np.isclose(eps, 3.6 + 4 / 10)
    assert "One-off charges" in note
    assert "3 of the last 4 quarters" in note


def test_immaterial_one_offs_ignored():
    data = quarterly(["2026-03-31", "2026-06-30"], [100] * 2, [20] * 2,
                     net=[10, 10], normalized=[10.1, 10])
    assert normalized_eps(2.0, data, 10) == (2.0, None)


def test_fiscal_year_labels():
    assert fy_label("2026-03-31") == "FY2026"
    assert fy_label("2025-12-31") == "FY2026"


def test_normalized_gap_without_one_offs_is_not_used():
    data = quarterly(["2026-03-31", "2026-06-30"], [100] * 2, [20] * 2,
                     net=[10, 10], normalized=[13, 13])     # no unusual items
    eps, note = normalized_eps(2.0, data, 10)

    assert eps == 2.0
    assert "not adjusted" in note
