from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hr_analytics.config import DATA_DIR
from hr_analytics.sample_data import generate_sample_workbook


if __name__ == "__main__":
    output = generate_sample_workbook(DATA_DIR / "sample_hr_helpline_workbook.xlsx")
    print(f"Sample workbook written to {Path(output).resolve()}")
