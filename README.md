# SOC 2 Sales Kit

Contents:
- `soc2_intake_workbook.xlsx` — client-facing intake workbook for SOC 2 sales and readiness discovery
- `soc2_readiness.py` — readiness calculator
- `portal_app_soc2.py` — updated Streamlit portal code with a SOC 2 dashboard section

## Run the portal
```bash
pip install streamlit pandas openpyxl
streamlit run portal_app_soc2.py
```

Open http://localhost:8501 and sign in with:
- username: `admin`
- password: `admin123`

## Supported uploads
- the included Excel workbook (`soc2_intake_workbook.xlsx`)
- a CSV export of the `Control Intake` sheet with the same column names

## Workbook notes
Blue cells are for client input. The `Summary Preview` sheet updates automatically and provides a lightweight readiness estimate.
