# Streamlit Community Cloud Deployment

This project is ready to deploy from a GitHub repository to Streamlit Community Cloud.

## Important Data Note

Do not commit local HR workbooks, SQLite databases, or API keys. The `.gitignore` file excludes:

- `data/*.sqlite`
- `data/*.xlsx`
- `.streamlit/secrets.toml`
- `.env`

Users should upload the Excel workbook through the app after deployment.

## GitHub Repository

Create a new GitHub repository, then add the project files from this folder.

If `git` is installed:

```powershell
cd "C:\Users\thoma\Documents\New project"
git init
git add .
git commit -m "Initial HR Helpline dashboard prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USER/YOUR-REPO.git
git push -u origin main
```

On this machine, `git` was not available at the time of setup. You can either install Git for Windows or upload the files through GitHub's web interface.

## Streamlit Community Cloud

1. Go to Streamlit Community Cloud.
2. Create a new app from your GitHub repository.
3. Select the repository and branch.
4. Set the main file path to:

```text
app.py
```

5. Deploy the app.

The repository root includes `requirements.txt`, which Streamlit Community Cloud uses to install dependencies.

## Secrets

In Streamlit Community Cloud, add secrets for:

```toml
OPENAI_API_KEY = "your_openai_api_key"
OPENAI_MODEL = "gpt-5.2"
```

The app also supports local environment variables with the same names.

## Local Storage Limitation

Streamlit Community Cloud local file storage is not guaranteed to persist. For this prototype, users should expect to upload the workbook again after app restarts. A future production version should move cleaned data to PostgreSQL or another managed database.

