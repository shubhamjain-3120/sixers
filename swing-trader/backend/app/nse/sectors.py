import io
import logging
import pandas as pd
from app.nse.http import fetch_nse_csv

logger = logging.getLogger(__name__)
NIFTY500_CSV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"


def build_sector_map() -> dict:
    """Returns {symbol: industry} from the Nifty 500 CSV."""
    raw = fetch_nse_csv(NIFTY500_CSV_URL)
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip() for c in df.columns]
    result = {}
    for _, row in df.iterrows():
        sym = str(row.get("Symbol", "")).strip()
        industry = str(row.get("Industry", "")).strip()
        if sym:
            result[sym] = industry
    return result
