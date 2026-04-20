# RiskNavigator SOC 2 Readiness App

A clean, deployment-ready Streamlit app for scoring SOC 2 readiness from a control intake workbook or CSV.

## Repo structure

```text
risknavigator-soc2/
├── app.py
├── soc2_readiness.py
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
└── sample_data/
    └── sample_control_intake.csv
```

## What this app does

- accepts a SOC 2 control intake workbook or CSV
- scores readiness by control area
- calculates an overall readiness score and band
- shows top blockers and recommended next actions
- exports scored controls, readiness JSON, and executive summary text

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud deployment

1. Create a new GitHub repository.
2. Upload all files from this folder.
3. In Streamlit Community Cloud, deploy the repo and set the main file to `app.py`.
4. Add secrets in the app settings using the values from `.streamlit/secrets.toml.example`.

## Suggested Streamlit secrets

```toml
[auth]
username = "your_admin_username"
password = "your_admin_password"
```

If no secrets are configured, the app falls back to demo access:

```text
admin / admin123
```

## Sample file

Use `sample_data/sample_control_intake.csv` to test the app immediately after deployment.

## GitHub upload checklist

Upload these files exactly:

- `app.py`
- `soc2_readiness.py`
- `requirements.txt`
- `.gitignore`
- `.streamlit/config.toml`
- `.streamlit/secrets.toml.example`
- `sample_data/sample_control_intake.csv`

## Notes

- `.streamlit/secrets.toml` should **not** be committed to GitHub.
- For Excel uploads, the workbook must contain a sheet named `Control Intake`.
