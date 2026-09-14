# PUMS-BENCH solution notes

All 38 answers have been computed locally. The primary implementation and an
independent SQLite implementation produce identical final answer strings for
all 38 questions. Five statistical edge-case tests also passed.
Local verification is not an online Kaggle score.

## Files and reproduction

- `results/submission.csv` is the final upload file. Preserve its answer strings
  and decimal places; opening and saving it in Excel can change formatting.
- `solve.py` implements the primary calculations; `verify_sql.py` independently
  verifies them using SQL.
- `README.md` provides reproduction commands; `requirements.txt` pins dependencies.
- `results/audit.json` contains unrounded values and all 80 replicate estimates
  for each standard-error question.
- `results/validation.json` records the individual verification results.

## Data verification

The inputs are the official Census Bureau ACS 1-year PUMS Texas archives.
Both 2024 SHA-256 hashes match the competition overview. The independently
downloaded 2023 archive hashes are also pinned in the code for reproducibility.

| Year | Person records | Housing and group quarters placeholder records | Total PWGTP |
|---|---:|---:|---:|
| 2024 | 292272 | 132629 | 31290831 |
| 2023 | 301984 | 135627 | 30503301 |

## Important definitions

1. Record counts and population estimates differ. Q001-Q006 are unweighted;
   subsequent questions use PWGTP or WGTP as specified.
2. SERIALNO remains a string. Person-to-household joins are many-to-one.
   Checks ensure every person matches, household keys are unique, and occupied
   households' member counts equal NP.
3. Occupied housing means TYPEHUGQ = 1 and NP >= 1. Renting requires TEN = 3;
   TEN = 4 is excluded. Owned housing has TEN = 1 or 2.
4. The income factors are 1.015250 for 2024 and 1.019518 for 2023. Q032 uses
   unrounded adjusted yearly medians. Q027 and Q028 use ADJHSG, whose 2024
   factor is 1.
5. A weighted median is the smallest distinct value at which cumulative
   weight reaches half the total. There is no interpolation or averaging of
   adjacent values.
6. Negative replicate weights are retained. Tied values must be grouped first;
   cumulative signed weights need not be monotone, so binary search is unsuitable.
7. Each replicate recomputes the complete statistic. The standard error is
   sqrt(sum((Xr - X)^2) / 20), for r = 1 through 80. Q038 uses percentage points.
8. Final rounding is half away from zero. Integer answers have no decimal point;
   decimal2 has two decimal places; percent1 has one and no percent sign.

## Complete answer table

Unless a question explicitly uses or compares 2023 data, calculations use 2024.
Income adjustment means multiplication by that year's ADJINC / 1000000.

| Question | Answer string | Statistic | Calculation |
|---|---:|---|---|
| q001 | `292272` | Person record count | Count all rows in the 2024 person file; no weights. |
| q002 | `60989` | Records aged 65 or older | Count person records with AGEP >= 65. |
| q003 | `119023` | Housing unit records | Count housing records with TYPEHUGQ = 1. |
| q004 | `148354` | Female records | Count person records with SEX = 2. |
| q005 | `6508` | Unemployed records | Count ESR = 3; exclude blank ESR values. |
| q006 | `8580` | Vacant housing units | Count TYPEHUGQ = 1 and NP = 0. |
| q007 | `4369909` | Population aged 65 or older | Sum PWGTP for AGEP >= 65. |
| q008 | `4126885` | Renter households | Sum WGTP for occupied housing units with TEN = 3. |
| q009 | `36.93` | Mean age | Sum AGEP * PWGTP and divide by total PWGTP. |
| q010 | `63643` | Mean employed civilian wage | ESR in {1,2}; include zero WAGP; use PWGTP and the income adjustment. |
| q011 | `35` | Median age | PWGTP-weighted median of all person ages. |
| q012 | `48732` | Median positive employed civilian wage | ESR in {1,2} and WAGP > 0; adjust the PWGTP-weighted wage median. |
| q013 | `79697` | Median household income | Adjust the WGTP-weighted HINCP median for occupied housing units. |
| q014 | `54` | Age at the 75th percentile | Smallest age at which cumulative PWGTP reaches 75% of total PWGTP. |
| q015 | `2.61` | Mean household size | WGTP-weighted mean NP for occupied housing units. |
| q016 | `24.5` | Population percentage under 18 | 100 times PWGTP for AGEP < 18 divided by total PWGTP. |
| q017 | `35.2` | Bachelor degree or higher percentage | Among AGEP >= 25, calculate the PWGTP percentage with SCHL >= 21. |
| q018 | `9721370` | Population in rental housing | Join on SERIALNO; sum PWGTP for persons in occupied units with TEN = 3. |
| q019 | `94012` | Person-weighted median household income | Attach HINCP to each person in occupied housing; take the PWGTP median and adjust. |
| q020 | `3.52` | Person-weighted mean household size | Attach NP to each person in occupied housing; calculate its PWGTP mean. |
| q021 | `5649594` | Female-householder households | Identify SPORDER = 1; sum WGTP once per occupied household with householder SEX = 2. |
| q022 | `49` | Median householder age | Take the WGTP-weighted age median of SPORDER = 1 householders in occupied housing. |
| q023 | `3133339` | Households with an older member | Sum WGTP once per occupied household having any member with AGEP >= 65. |
| q024 | `625825` | Group quarters population | Join on SERIALNO; sum PWGTP where TYPEHUGQ is 2 or 3. |
| q025 | `66.9` | Population percentage in owned housing | Among persons in occupied housing, calculate the PWGTP percentage with TEN in {1,2}. |
| q026 | `58681` | Median income with an older householder | Occupied households with householder AGEP >= 65; adjust the WGTP-weighted HINCP median. |
| q027 | `1482` | Median gross rent | Occupied units with nonmissing GRNTP; take the WGTP median and apply ADJHSG. |
| q028 | `300000` | Median owned property value | Occupied units with TEN in {1,2} and nonmissing VALP; take the WGTP median and apply ADJHSG. |
| q029 | `35` | 2023 median age | Use the 2023 person file and its PWGTP weights. |
| q030 | `787530` | Population growth | Total 2024 PWGTP minus total 2023 PWGTP. |
| q031 | `76260` | 2023 median household income | Use occupied 2023 households, WGTP, and the 2023 income adjustment. |
| q032 | `4.5` | Median income percentage change | Use unrounded adjusted yearly medians: 100 * (2024 - 2023) / 2023. |
| q033 | `87774` | Change in renter households | 2024 renter WGTP total minus the corresponding 2023 total. |
| q034 | `4307` | Older population standard error | Recalculate q007 using each of the 80 PWGTP replicate columns. |
| q035 | `23195` | Renter household standard error | Recalculate q008 using each of the 80 WGTP replicate columns. |
| q036 | `241` | Mean wage standard error | Recalculate q010 with the same replicate weights in numerator and denominator. |
| q037 | `646` | Median household income standard error | Recalculate all 80 adjusted weighted medians for q013 without intermediate rounding. |
| q038 | `0.13` | Education percentage standard error | Recalculate all 80 percentages for q017; report the standard error in percentage points. |

## Submission materials

Submit results/submission.csv to Kaggle and provide the reproducible repository
link as required by the competition and the course. Raw archives do not need to
be published: the download script obtains and verifies them from the official
source.

See README.md for official documentation links and full reproduction commands.
