# Raw data sources

All files downloaded 2026-11-08 unless noted.

## Census BTOS (`raw/btos/`)

Links taken from the "Data Downloads" page of the BTOS site (https://www.census.gov/hfp/btos),
which is a JavaScript app; file paths were read from its bundle (`js/app.33f77371.js`,
`currentDocuments` / `oldDocuments` lists), not guessed.

| File | URL | Notes |
|---|---|---|
| `National.xlsx` | https://www.census.gov/hfp/btos/downloads/National.xlsx | Current file ("National") |
| `Sector.xlsx` | https://www.census.gov/hfp/btos/downloads/Sector.xlsx | Current file ("Sector") |
| `Employment Size Class.xlsx` | https://www.census.gov/hfp/btos/downloads/Employment%20Size%20Class.xlsx | Current file ("Employment size class") |
| `AI Core Questions.xlsx` | https://www.census.gov/hfp/btos/downloads/AI%20Core%20Questions.xlsx | Archive file "AI Core Questions (Original)", 09/11/2023 to 10/05/2025: the old "producing goods or services" wording |

There is no separate collection/reference dates download: each workbook has a
`Collection and Reference Dates` sheet.

## Census SUSB (`raw/susb/`)

| File | URL | Notes |
|---|---|---|
| `us_state_naics_detailedsizes_2022.xlsx` | https://www2.census.gov/programs-surveys/susb/tables/2022/us_state_naics_detailedsizes_2022.xlsx | "U.S. & states, NAICS, detailed employment sizes", 2022 (released 4/10/2025). Listed on https://www.census.gov/data/tables/2022/econ/susb/2022-susb-annual.html. The 2023 and 2024 annual table pages return 404, so 2022 is the latest available. |

## Ramp AI Index (`raw/ramp/`)

FRED release "Ramp AI Index". Downloaded 2026-11-08 through the FRED API
(`https://api.stlouisfed.org/fred/series/observations?series_id=<ID>`, API key from the
`FRED_API_KEY` environment variable, never stored in files) and saved as `raw/ramp/<ID>.csv`.
Series IDs confirmed with the API's series search (all updated 2026-10-14, data through 2026-09):

| ID | FRED title (after "Artificial Intelligence Adoption by Ramp Businesses:") |
|---|---|
| RAMPAIALL | Overall |
| RAMPAISMB / RAMPAIMIDMARKET / RAMPAIENTERPRISE | Company Size: Small / Medium-Sized / Large Businesses |
| RAMPAITECH | Industry: Information |
| RAMPAIFINANCE | Industry: Finance and Insurance |
| RAMPAIMANUFACTURING | Industry: Manufacturing |
| RAMPAIRETAIL | Industry: Retail Trade |
| RAMPAICONSTRUCTION | Industry: Construction |
| RAMPAIHEALTHCARE | Industry: Health Care and Social Assistance |
| RAMPAIHOSPITALITY | Industry: Accommodation and Food Services |

Not used: RAMPAIOPENAI, RAMPAIANTHROPIC, RAMPAIXAI (provider series).
Without an API key the script falls back to `fredgraph.csv`, which blocked scripted
requests from this machine on 2026-11-08.
