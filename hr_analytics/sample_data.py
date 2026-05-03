from __future__ import annotations

from pathlib import Path
import random

import pandas as pd


SAMPLE_EMPLOYEES = [
    ("Alex", "Taylor"),
    ("Morgan", "Reid"),
    ("Sam", "Patel"),
    ("Jamie", "Campbell"),
    ("Riley", "Fraser"),
    ("Casey", "Brown"),
]

SAMPLE_CATEGORIES = [
    "Recruitment",
    "Contracts",
    "Pay and Reward",
    "Annual Leave",
    "Sickness Absence",
    "People System Access",
    "Policy Guidance",
    "Onboarding",
]

SAMPLE_CHANNELS = ["E-Mail", "Web", "Phone"]
SAMPLE_STATUSES = ["Closed", "Resolved", "Waiting", "New", "In Progress", "Review Update"]


def generate_sample_raw_workbook(seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    random.seed(seed)
    start_date = pd.Timestamp("2025-01-01")
    end_date = pd.Timestamp("2025-06-30")
    business_days = list(pd.bdate_range(start_date, end_date))

    call_rows = []
    for index in range(1, 241):
        reported_date = random.choice(business_days) + pd.Timedelta(hours=random.randint(8, 16), minutes=random.randint(0, 59))
        status = random.choices(SAMPLE_STATUSES, weights=[55, 15, 15, 7, 5, 3], k=1)[0]
        first_name, last_name = random.choice(SAMPLE_EMPLOYEES)
        category = random.choice(SAMPLE_CATEGORIES)
        interactions = random.randint(1, 9)
        resolution_offset = max(0, int(random.gauss(4, 3)))
        resolution_date = reported_date.normalize() + pd.Timedelta(days=resolution_offset)
        if status not in {"Closed", "Resolved"}:
            resolution_date = pd.NaT
        call_rows.append(
            {
                "SR Number": f"SR_SAMPLE_{index:05d}",
                "Date Reported": reported_date,
                "Severity": random.choice(["Low", "Medium"]),
                "Status": status,
                "Status Type": "Closed" if status in {"Closed", "Resolved"} else "Open",
                "SR Title": f"{category} enquiry about {random.choice(['process', 'form', 'approval', 'system access'])}",
                "Last Queue Assigned Date": reported_date,
                "Last Response Date": reported_date + pd.Timedelta(days=random.randint(0, 4)),
                "Channel Type": random.choices(SAMPLE_CHANNELS, weights=[65, 28, 7], k=1)[0],
                "Handler_First Name": first_name,
                "Handler_Last Name": last_name,
                "Queue Name": "HR Helpline",
                "SR Resolution Date": resolution_date,
                "Average Time to Resolve (Days)": resolution_offset if pd.notna(resolution_date) else pd.NA,
                "No of Interactions to Resolve an SR": interactions,
                "No of First Response Compliant SRs": random.choices([1, 0], weights=[86, 14], k=1)[0],
                "Total Rows": 1,
                "Milestone Code": "FirstResponseMetricCode",
                "Milestone Status": "Complete",
                "Completion Date and Time": resolution_date,
                "Category Name": category,
            }
        )

    dates = pd.date_range(start_date, end_date, freq="D")
    sickness = pd.DataFrame({"Dates": dates})
    annual_leave = pd.DataFrame({"Dates": dates})
    for first_name, _ in SAMPLE_EMPLOYEES:
        sickness[first_name] = pd.NA
        annual_leave[first_name] = pd.NA
        sick_days = random.sample(list(pd.bdate_range(start_date, end_date)), k=4)
        leave_days = random.sample(list(pd.bdate_range(start_date, end_date)), k=10)
        sickness.loc[sickness["Dates"].isin(sick_days), first_name] = 1
        annual_leave.loc[annual_leave["Dates"].isin(leave_days), first_name] = 1

    return pd.DataFrame(call_rows), sickness, annual_leave


def generate_sample_workbook(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sr_data, sickness, annual_leave = generate_sample_raw_workbook()
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        sr_data.to_excel(writer, sheet_name="SR Data", index=False)
        sickness.to_excel(writer, sheet_name="Sickness", index=False)
        annual_leave.to_excel(writer, sheet_name="Annual leave", index=False)
    return output_path

