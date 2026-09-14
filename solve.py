"""Reproduce all 38 PUMS-BENCH answers from official ACS Texas ZIP files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

CHECKSUMS = {
    '2024/csv_ptx.zip': '42ad7127988234d7dd30c23df8ada371b2135b5db912d2e634a6f901477afe63',
    '2024/csv_htx.zip': '59274006389de6f8d6ee5f6e2eb48f7f1ccd4d3c9f730df857be641d5ef65b94',
    '2023/csv_ptx.zip': 'd84255b4ab9ec48e899614320ffe272afb49af03132b1ead60188b0f5b51909e',
    '2023/csv_htx.zip': 'cce750723979195edc594cf9808290ba688c2462298a0c7d62bd2713dd469a1a',
}
P_COLS = 'SERIALNO SPORDER AGEP SEX ESR SCHL WAGP ADJINC PWGTP'.split()
H_COLS = 'SERIALNO TYPEHUGQ NP TEN HINCP GRNTP VALP ADJINC ADJHSG WGTP'.split()


def dec(value):
    if isinstance(value, Fraction):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return value if isinstance(value, Decimal) else Decimal(str(value))


def formatted(value, kind):
    digits = {'integer': 0, 'decimal2': 2, 'percent1': 1}[kind]
    with localcontext() as ctx:
        ctx.prec = 50
        return format(dec(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP), f'.{digits}f')


def as_int(values):
    a = np.asarray(values)
    assert np.isfinite(a).all(), 'Unexpected missing value within the question universe'
    b = a.astype(np.int64)
    assert np.array_equal(a, b), 'Expected integer Census values'
    return b


def total(frame, weight):
    return int(as_int(frame[weight]).sum())


def mean(frame, value, weight):
    x, w = as_int(frame[value]), as_int(frame[weight])
    assert int(w.sum()) > 0
    return Fraction(int(np.dot(x, w)), int(w.sum()))


def quantile(frame, value, weight, fraction=Fraction(1, 2)):
    """Smallest DISTINCT value satisfying cumulative signed weight >= threshold.

    Group ties before evaluating the CDF. Replicate weights may be negative, so
    cumulative weights need not be monotone; binary search is not valid here.
    """
    x, w = as_int(frame[value]), as_int(frame[weight])
    order = np.argsort(x, kind='stable')
    x, w = x[order], w[order]
    end_of_tie = np.r_[x[1:] != x[:-1], True]
    cumulative = np.cumsum(w)[end_of_tie]
    threshold = int(w.sum()) * fraction.numerator
    assert int(w.sum()) > 0
    qualifying = np.flatnonzero(cumulative * fraction.denominator >= threshold)
    assert len(qualifying) > 0
    return int(x[end_of_tie][qualifying[0]])


def factor(frame, name):
    values = frame[name].unique()
    assert len(values) == 1 and not pd.isna(values[0]), f'{name} must be constant in a 1-year release'
    return Fraction(int(values[0]), 1_000_000)


def occupied(frame):
    return frame.TYPEHUGQ.eq(1) & frame.NP.ge(1)


def renters(frame):
    return occupied(frame) & frame.TEN.eq(3)


def load(data_dir, year, kind):
    key = f'{year}/csv_{kind}tx.zip'
    path = data_dir / key
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == CHECKSUMS[key], f'Checksum mismatch: {key}: {digest}'
    columns = (P_COLS if kind == 'p' else H_COLS).copy()
    if year == 2024:
        prefix = 'PWGTP' if kind == 'p' else 'WGTP'
        columns += [f'{prefix}{r}' for r in range(1, 81)]
    with zipfile.ZipFile(path) as z:
        candidates = [n for n in z.namelist() if Path(n).name == f'psam_{kind}48.csv']
        assert len(candidates) == 1
        with z.open(candidates[0]) as f:
            frame = pd.read_csv(f, usecols=columns, dtype={'SERIALNO': 'string'})
    assert frame.SERIALNO.notna().all()
    if kind == 'h':
        assert frame.SERIALNO.is_unique
    else:
        assert not frame.duplicated(['SERIALNO', 'SPORDER']).any()
    print(f'Loaded {key}: {len(frame):,} rows; checksum verified', flush=True)
    return frame


def solve(data_dir):
    p, h = load(data_dir, 2024, 'p'), load(data_dir, 2024, 'h')
    p23, h23 = load(data_dir, 2023, 'p'), load(data_dir, 2023, 'h')
    inc, inc23, hsg = factor(h, 'ADJINC'), factor(h23, 'ADJINC'), factor(h, 'ADJHSG')
    assert factor(p, 'ADJINC') == inc
    assert factor(p23, 'ADJINC') == inc23
    occ, occ23 = h.loc[occupied(h)], h23.loc[occupied(h23)]
    rent, rent23 = h.loc[renters(h)], h23.loc[renters(h23)]
    old = p.loc[p.AGEP.ge(65)]
    employed = p.loc[p.ESR.isin([1, 2])]
    adults = p.loc[p.AGEP.ge(25)]
    educated = adults.loc[adults.SCHL.ge(21)]
    assert occ.HINCP.notna().all() and employed.WAGP.notna().all()
    # Every person must link to exactly one household / GQ placeholder.
    joined = p[['SERIALNO', 'PWGTP']].merge(
        h[['SERIALNO', 'TYPEHUGQ', 'NP', 'TEN', 'HINCP']],
        on='SERIALNO', how='left', validate='many_to_one', indicator=True)
    assert joined['_merge'].eq('both').all() and len(joined) == len(p)
    persons_occ = joined.loc[occupied(joined)]
    heads = p.loc[p.SPORDER.eq(1), ['SERIALNO', 'AGEP', 'SEX']]
    household_heads = occ.merge(heads, on='SERIALNO', how='left', validate='one_to_one')
    assert household_heads.AGEP.notna().all()
    # Data integrity: the number of linked records must equal the household NP.
    person_counts = p.groupby('SERIALNO').size()
    assert np.array_equal(occ.SERIALNO.map(person_counts).to_numpy(), occ.NP.to_numpy())
    result = {}
    def put(n, v):
        result[f'q{n:03d}'] = v
    put(1, len(p))
    put(2, len(old))
    put(3, int(h.TYPEHUGQ.eq(1).sum()))
    put(4, int(p.SEX.eq(2).sum()))
    put(5, int(p.ESR.eq(3).sum()))
    put(6, int((h.TYPEHUGQ.eq(1) & h.NP.eq(0)).sum()))
    put(7, total(old, 'PWGTP'))
    put(8, total(rent, 'WGTP'))
    put(9, mean(p, 'AGEP', 'PWGTP'))
    put(10, mean(employed, 'WAGP', 'PWGTP') * inc)
    put(11, quantile(p, 'AGEP', 'PWGTP'))
    put(12, quantile(employed.loc[employed.WAGP.gt(0)], 'WAGP', 'PWGTP') * inc)
    put(13, quantile(occ, 'HINCP', 'WGTP') * inc)
    put(14, quantile(p, 'AGEP', 'PWGTP', Fraction(3, 4)))
    put(15, mean(occ, 'NP', 'WGTP'))
    put(16, Fraction(100 * total(p.loc[p.AGEP.lt(18)], 'PWGTP'), total(p, 'PWGTP')))
    put(17, Fraction(100 * total(educated, 'PWGTP'), total(adults, 'PWGTP')))
    put(18, total(joined.loc[renters(joined)], 'PWGTP'))
    put(19, quantile(persons_occ, 'HINCP', 'PWGTP') * inc)
    put(20, mean(persons_occ, 'NP', 'PWGTP'))
    put(21, total(household_heads.loc[household_heads.SEX.eq(2)], 'WGTP'))
    put(22, quantile(household_heads, 'AGEP', 'WGTP'))
    put(23, total(occ.loc[occ.SERIALNO.isin(old.SERIALNO)], 'WGTP'))
    put(24, total(joined.loc[joined.TYPEHUGQ.isin([2, 3])], 'PWGTP'))
    put(25, Fraction(100 * total(persons_occ.loc[persons_occ.TEN.isin([1, 2])], 'PWGTP'), total(persons_occ, 'PWGTP')))
    put(26, quantile(household_heads.loc[household_heads.AGEP.ge(65)], 'HINCP', 'WGTP') * inc)
    put(27, quantile(occ.loc[occ.GRNTP.notna()], 'GRNTP', 'WGTP') * hsg)
    put(28, quantile(occ.loc[occ.TEN.isin([1, 2]) & occ.VALP.notna()], 'VALP', 'WGTP') * hsg)
    put(29, quantile(p23, 'AGEP', 'PWGTP'))
    put(30, total(p, 'PWGTP') - total(p23, 'PWGTP'))
    put(31, quantile(occ23, 'HINCP', 'WGTP') * inc23)
    put(32, 100 * (result['q013'] - result['q031']) / result['q031'])
    put(33, total(rent, 'WGTP') - total(rent23, 'WGTP'))

    replicates = {}
    def se(n, full, estimates):
        estimates = list(estimates)
        assert len(estimates) == 80
        with localcontext() as ctx:
            ctx.prec = 50
            x = dec(full)
            xr = [dec(v) for v in estimates]
            value = (sum((v - x) ** 2 for v in xr) / Decimal(20)).sqrt()
            put(n, value)
            replicates[f'q{n:03d}'] = {'full': str(x), 'replicates': [str(v) for v in xr]}

    se(34, result['q007'], (total(old, f'PWGTP{r}') for r in range(1, 81)))
    se(35, result['q008'], (total(rent, f'WGTP{r}') for r in range(1, 81)))
    se(36, result['q010'], (mean(employed, 'WAGP', f'PWGTP{r}') * inc for r in range(1, 81)))
    se(37, result['q013'], (quantile(occ, 'HINCP', f'WGTP{r}') * inc for r in range(1, 81)))
    se(38, result['q017'], (Fraction(100 * total(educated, f'PWGTP{r}'), total(adults, f'PWGTP{r}')) for r in range(1, 81)))
    diagnostics = {
        'checksums': CHECKSUMS,
        'rows': {'p2024': len(p), 'h2024': len(h), 'p2023': len(p23), 'h2023': len(h23)},
        'population': {'2024': total(p, 'PWGTP'), '2023': total(p23, 'PWGTP')},
        'adjustment': {'income2024': str(inc), 'income2023': str(inc23), 'housing2024': str(hsg)},
        'unrounded_answers': {q: str(v) for q, v in result.items()},
        'standard_error_details': replicates,
        'integrity_checks': ['unique household keys', 'unique person keys', 'all persons matched', 'NP equals member count', 'one householder per occupied unit', 'required values nonmissing', 'year-specific adjustment factors constant'],
    }
    return result, diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--output-dir', type=Path, default=Path('results'))
    args = parser.parse_args()
    results, diagnostics = solve(args.data_dir)
    decimals = {9: 'decimal2', 15: 'decimal2', 20: 'decimal2', 38: 'decimal2',
                16: 'percent1', 17: 'percent1', 25: 'percent1', 32: 'percent1'}
    rows = []
    for n in range(1, 39):
        q = f'q{n:03d}'
        kind = decimals.get(n, 'integer')
        answer = formatted(results[q], kind)
        assert re.fullmatch({'integer': r'-?\d+', 'decimal2': r'-?\d+\.\d{2}', 'percent1': r'-?\d+\.\d'}[kind], answer)
        rows.append((q, answer))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'submission.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['question_id', 'answer'])
        writer.writerows(rows)
    (args.output_dir / 'audit.json').write_text(json.dumps(diagnostics, indent=2), encoding='utf-8')
    print('\n'.join(f'{q},{a}' for q, a in rows))
    print(f'Wrote {args.output_dir / "submission.csv"}', flush=True)


if __name__ == '__main__':
    main()
