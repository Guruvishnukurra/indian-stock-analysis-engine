import pandas as pd


def calculate_price_features(price_data):
    """
    Calculate basic price, return, moving-average,
    and volatility features.
    """

    data = price_data.copy()

    data["Daily_Return"] = (
        data["Close"].pct_change() * 100
    )

    data["SMA_20"] = (
        data["Close"].rolling(window=20).mean()
    )

    data["SMA_50"] = (
        data["Close"].rolling(window=50).mean()
    )

    data["SMA_200"] = (
        data["Close"].rolling(window=200).mean()
    )

    data["Volatility_30"] = (
        data["Daily_Return"]
        .rolling(window=30)
        .std()
    )

    data["Return_7D"] = (
        data["Close"].pct_change(7) * 100
    )

    data["Return_30D"] = (
        data["Close"].pct_change(30) * 100
    )

    return data


def calculate_rsi(price_data, window=14):
    """
    Calculate Relative Strength Index (RSI).
    """

    data = price_data.copy()

    delta = data["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    rs = avg_gain / avg_loss

    data["RSI_14"] = (
        100 - (100 / (1 + rs))
    )

    return data


def calculate_macd(price_data):
    """
    Calculate MACD, signal line, and histogram.
    """

    data = price_data.copy()

    ema_12 = (
        data["Close"]
        .ewm(span=12, adjust=False)
        .mean()
    )

    ema_26 = (
        data["Close"]
        .ewm(span=26, adjust=False)
        .mean()
    )

    data["MACD"] = ema_12 - ema_26

    data["MACD_Signal"] = (
        data["MACD"]
        .ewm(span=9, adjust=False)
        .mean()
    )

    data["MACD_Histogram"] = (
        data["MACD"] -
        data["MACD_Signal"]
    )

    return data


def calculate_volume_features(price_data):
    """
    Calculate volume-related features.

    Infinite percentage changes caused by zero-volume
    days are converted to NaN.
    """

    data = price_data.copy()

    data["Volume_Change"] = (
        data["Volume"].pct_change() * 100
    )

    data["Volume_Change"] = (
        data["Volume_Change"]
        .replace([float("inf"), float("-inf")], pd.NA)
    )

    data["Volume_SMA_20"] = (
        data["Volume"]
        .rolling(window=20)
        .mean()
    )

    return data


def calculate_technical_features(price_data):
    """
    Calculate all technical indicators and features.
    """

    data = calculate_price_features(price_data)

    data = calculate_rsi(data)

    data = calculate_macd(data)

    data = calculate_volume_features(data)

    return data