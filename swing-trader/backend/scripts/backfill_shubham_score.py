"""One-off: compute shubham_score for existing DailyScan rows that don't have it.

Reads signal fields already on each row — no OHLCV refetch needed.
Run from the backend directory:
    python3 -m scripts.backfill_shubham_score
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models import DailyScan
from app.scanner.signals import SignalsBundle
from app.scanner.scorer import compute_shubham_score


def main():
    db = SessionLocal()
    try:
        rows = db.query(DailyScan).all()
        updated = 0
        skipped = 0
        for r in rows:
            if r.shubham_score is not None:
                skipped += 1
                continue
            # Some old rows may have NULLs on required signals; default sensibly.
            sig = SignalsBundle(
                rsi_14=r.rsi_14 or 50.0,
                pct_below_20d_high=r.pct_below_20d_high or 0.0,
                pct_below_50d_high=r.pct_below_50d_high or 0.0,
                dist_from_20dma_pct=r.dist_from_20dma_pct or 0.0,
                dist_from_50dma_pct=r.dist_from_50dma_pct or 0.0,
                volume_ratio=r.volume_ratio or 0.0,
                swing_low_30d=r.swing_low_30d or 0.0,
                swing_high_30d=r.swing_high_30d or 0.0,
                pivot_support=r.pivot_support or 0.0,
                pivot_resistance=r.pivot_resistance or 0.0,
                green_after_red=bool(r.green_after_red),
            )
            r.shubham_score = compute_shubham_score(sig)
            updated += 1
        db.commit()
        print(f"Backfill complete: updated={updated}, already_set={skipped}, total={len(rows)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
