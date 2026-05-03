from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

APP_NAME = "HR Helpline Analytics"
ORGANISATION_NAME = "The University of Edinburgh"

SQLITE_PATH = DATA_DIR / "hr_helpline.sqlite"
DATABASE_URL = os.getenv("HR_HELPLINE_DATABASE_URL", f"sqlite:///{SQLITE_PATH.as_posix()}")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")

AUTH_ENABLED = False
PROTOTYPE_USER = "Local prototype user"

CLOSED_STATUS_KEYWORDS = (
    "closed",
    "resolved",
    "complete",
    "completed",
    "done",
)

UNKNOWN_HANDLER = "Unassigned / Unknown"
UNKNOWN_CATEGORY = "Uncategorised"
UNKNOWN_TEXT = "Unknown"

EXPECTED_SR_COLUMNS = {
    "sr_number": "SR Number",
    "date_reported": "Date Reported",
    "status": "Status",
    "channel_type": "Channel Type",
    "handler_first_name": "Handler First Name",
    "handler_last_name": "Handler Last Name",
    "resolution_date": "Resolution Date",
    "category_name": "Category Name",
    "average_time_to_resolve": "Average Time to Resolve",
    "number_of_interactions": "Number of Interactions",
    "first_response_compliant": "First Response Compliant",
}
