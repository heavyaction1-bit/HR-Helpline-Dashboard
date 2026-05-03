# HR Helpline Analytics Dashboard Prototype

Streamlit prototype for analysing HR Helpline service request data for The University of Edinburgh.

The app lets you upload an Excel workbook and creates dashboards for:

- Whole-team case volumes, channels, statuses, categories, and response compliance
- Individual workload and performance context, including absence and annual leave
- Resource impact analysis connecting leave/sickness, available staff days, case demand, and handling outcomes
- Core team selection to exclude occasional handlers from dashboard metrics
- Name matching so short names and alternate spellings can be merged into one staff record
- Individual staff report preview and export for workload/performance conversations
- ChatGPT Insights tab for asking questions about the currently scoped dashboard data
- Customer query/category analysis
- Absence and leave trends
- Data quality checks for missing dates, missing handlers, duplicates, and invalid durations

This is a local prototype only. It does not include real authentication, row-level permissions, or audit logging yet.

## Install

```bash
pip install -r requirements.txt
```

## Run Locally

```bash
streamlit run app.py
```

If your Python scripts folder is not on `PATH`, run:

```bash
python -m streamlit run app.py
```

Open the local URL shown by Streamlit, usually `http://localhost:8501`.

## ChatGPT Insights

The **ChatGPT Insights** tab can call the OpenAI API using the currently scoped dashboard data.

Set an API key before running the app:

```bash
$env:OPENAI_API_KEY="your_api_key_here"
```

Optionally set the model:

```bash
$env:OPENAI_MODEL="gpt-5.2"
```

If no environment key is set, the tab provides a temporary password field for local testing. The app sends data only when you click **Ask ChatGPT**.

## Streamlit Community Cloud

This app can be deployed from GitHub to Streamlit Community Cloud.

- Main file path: `app.py`
- Dependencies: `requirements.txt`
- Secrets: add `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in Streamlit Community Cloud secrets
- Do not commit local workbook files, SQLite files, `.env`, or `.streamlit/secrets.toml`

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full deployment checklist.

## Expected Workbook Structure

Upload an Excel workbook with these sheets:

- `SR Data`
- `Sickness`
- `Annual leave`

`SR Data` should contain one service request per row. Supported fields include:

- `SR Number`
- `Date Reported`
- `Status`
- `Channel Type`
- `Handler First Name` / `Handler_First Name`
- `Handler Last Name` / `Handler_Last Name`
- `Resolution Date` / `SR Resolution Date`
- `Category Name`
- `Average Time to Resolve`
- `Number of Interactions`
- `First Response Compliant`

The absence sheets are expected to be wide daily sheets:

- One date column, such as `Dates`
- One column per employee
- Daily markers such as `1` for sickness or annual leave

The loader ignores blank markers and zeroes.

## Local Database

Cleaned data is stored in a local SQLite database at:

```text
data/hr_helpline.sqlite
```

The database helper uses SQLAlchemy and reads the database URL from `HR_HELPLINE_DATABASE_URL`, so it can later be moved to PostgreSQL with fewer code changes.

## Sample Data

If you do not have a workbook available, use the **Load sample data** button in the sidebar.

You can also generate a sample workbook:

```bash
python scripts/generate_sample_data.py
```

This creates:

```text
data/sample_hr_helpline_workbook.xlsx
```

## Assumptions

- Statuses containing `closed`, `resolved`, `complete`, `completed`, or `done` are treated as closed/resolved.
- All other statuses are treated as open/active.
- Estimated working days are Monday to Friday within the selected date range.
- Available working days are estimated working days minus sickness and annual leave days.
- Absence sheets may use first names while SR Data uses full names. The prototype maps a first name to a handler only when it uniquely matches a handler first name.
- The sidebar Name matching tool can merge aliases, short names, and alternate spellings into a main staff record for the current Streamlit session.
- Case complexity, allocation method, part-time patterns, and non-case duties are not fully modelled in this prototype.

## Project Structure

```text
app.py
hr_analytics/
  config.py
  data_loader.py
  transformations.py
  metrics.py
  database.py
  sample_data.py
  security.py
  dashboard/
    components.py
    filters.py
    team_overview.py
    employee_performance.py
    customer_query.py
    absence_leave.py
    data_quality.py
scripts/
  generate_sample_data.py
data/
requirements.txt
FUTURE_IMPROVEMENTS.md
```

## Notes on Sensitive Data

This prototype is designed for local development. Before live use, add authentication, role-based access, audit logging, retention rules, and a data protection review.
