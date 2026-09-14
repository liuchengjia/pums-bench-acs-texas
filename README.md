# PUMS-BENCH reproducible solution

Computes the 38 deterministic ACS PUMS Texas answers for the course competition.
The CSV is generated entirely from the official 2023 and 2024 ACS **1-year** PUMS
person and housing files. No prediction model or answer-key lookup is used.

## Reproduce

Use Python 3.11 or newer (verified with the local bundled Python), then run from
this directory:

```sh
python -m pip install -r requirements.txt
python download_data.py --data-dir data
python solve.py --data-dir data --output-dir results
python test_statistics.py
python verify_sql.py --data-dir data --results-dir results
```

The download is approximately 148 MB. The ZIP archives can be read directly;
manual extraction is unnecessary. Existing files are reused only after their
SHA-256 checksum is verified. A mismatch stops execution.

## Deliverables

- `results/submission.csv`: exactly 38 rows, header `question_id,answer`.
- `solve.py`: primary NumPy/pandas implementation; integer arithmetic and exact
  fractions for totals, ratios, and dollar adjustments, followed by Decimal
  rounding. Standard errors use 50-digit Decimal arithmetic.
- `verify_sql.py`: independently reads the CSV files and checks all answers using
  SQLite aggregation, joins, grouped cumulative weights, and window functions.
- `test_statistics.py`: five targeted tests for rounding, exact-half medians,
  negative weights, tied values with negative weights, and zero wages.
- `results/audit.json`: input checksums, row counts, unrounded answers, data
  integrity checks, and all 80 replicate estimates for each SE question.
- `results/validation.json`: independent SQL comparison results.
- `solution_notes.md`: explanation and complete answer table.

## Statistical choices

Each question's universe is enforced explicitly. Occupied units have
`TYPEHUGQ=1 AND NP>=1`; renter units additionally have `TEN=3`. `TEN=4` is not
renting. Person estimates use `PWGTP`; household estimates use `WGTP` once per
household. Joins preserve the string `SERIALNO` and validate their cardinality.
The assignment defines householders as the person with `SPORDER=1`.

Weighted quantiles return the smallest distinct value whose cumulative weight
reaches the specified fraction of the total. Ties are grouped before testing
the threshold. Signed replicate weights are preserved, and the first qualifying
value is found without assuming that cumulative weights are monotone.

Income adjustments use the release's own `ADJINC/1,000,000`: 1.015250 for 2024
and 1.019518 for 2023. The 2024 housing adjustment is 1.000000. Q032 uses
unrounded year-specific adjusted medians. Q010 and Q036 include employed people
with zero wage income. Zero and negative household incomes are included.

For Q034-Q038, every replicate recomputes the whole statistic using its own
weight column, including both parts of a ratio. The final standard error is
`sqrt(sum((replicate - full)**2)/20)`. Values are rounded only at final output,
using half away from zero. Percent answers do not contain a percent symbol.

## Official sources

- [2024 ACS 1-year PUMS directory](https://www2.census.gov/programs-surveys/acs/data/pums/2024/1-Year/)
- [2023 ACS 1-year PUMS directory](https://www2.census.gov/programs-surveys/acs/data/pums/2023/1-Year/)
- [2024 data dictionary](https://www2.census.gov/programs-surveys/acs/tech_docs/pums/data_dict/PUMS_Data_Dictionary_2024.txt)
- [2023 data dictionary](https://www2.census.gov/programs-surveys/acs/tech_docs/pums/data_dict/PUMS_Data_Dictionary_2023.txt)
- [2024 Accuracy of the Data, pp. 12-13](https://www2.census.gov/programs-surveys/acs/tech_docs/pums/accuracy/2024AccuracyPUMS.pdf)
- [Competition](https://www.kaggle.com/competitions/pums-bench-deterministic-analytics-over-acs-pums)

The 2024 archive hashes match the hashes published in the competition overview.
The 2023 hashes pin the files independently downloaded from the specified official
directory; the competition overview did not publish 2023 hashes.

## Validation

All 38 final answer strings agree with an independent SQLite implementation.
Five statistical edge-case tests passed. This verification is not a Kaggle score.
The competition's question files and large raw data archives are excluded from
this repository; the download script obtains the required official archives.
