"""Independent SQLite implementation cross-checks every submitted answer.

Unlike solve.py's integer/Fraction and NumPy path, this verifier uses SQL joins,
GROUP BY, window sums, and SQL arithmetic against independently read CSV files.
"""
import argparse
import csv
import json
import math
import sqlite3
import zipfile
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--results-dir', type=Path, default=Path('results'))
    args = parser.parse_args()
    db = sqlite3.connect(':memory:')
    for year in (2023, 2024):
        for kind in ('p', 'h'):
            cols = ('SERIALNO SPORDER AGEP SEX ESR SCHL WAGP ADJINC PWGTP' if kind == 'p'
                    else 'SERIALNO TYPEHUGQ NP TEN HINCP GRNTP VALP ADJINC ADJHSG WGTP').split()
            prefix = 'PWGTP' if kind == 'p' else 'WGTP'
            if year == 2024:
                cols += [f'{prefix}{i}' for i in range(1,81)]
            with zipfile.ZipFile(args.data_dir / str(year) / f'csv_{kind}tx.zip') as z:
                filename = next(n for n in z.namelist() if Path(n).name == f'psam_{kind}48.csv')
                with z.open(filename) as f:
                    frame = pd.read_csv(f, usecols=cols, dtype={'SERIALNO': str})
            table = f'{kind}{year}'
            frame.to_sql(table, db, index=False)
            db.execute(f'CREATE INDEX {table}_serial ON {table}(SERIALNO)')
            print(f'SQL loaded {table}', flush=True)
    def sql(query):
        return db.execute(query).fetchone()[0]
    def stat(expr, table='p2024', where='1'):
        return sql(f'SELECT {expr} FROM {table} WHERE {where}')
    def median(value, weight, table, where='1', fraction=.5):
        return sql(f'''WITH grouped AS (
          SELECT {value} AS value, SUM({weight}) AS w FROM {table}
          WHERE {where} GROUP BY {value}
        ), cdf AS (
          SELECT value, SUM(w) OVER(ORDER BY value ROWS UNBOUNDED PRECEDING) AS c,
          SUM(w) OVER() AS t FROM grouped
        ) SELECT MIN(value) FROM cdf WHERE c >= {fraction} * t''')
    occ = 'TYPEHUGQ=1 AND NP>=1'
    rent = occ + ' AND TEN=3'
    emp = 'ESR IN (1,2)'
    adult = 'AGEP>=25'
    educated = adult + ' AND SCHL>=21'
    join = 'p2024 p JOIN h2024 h ON p.SERIALNO=h.SERIALNO'
    heads = join
    hh_occ = occ + ' AND p.SPORDER=1'
    inc = stat('MAX(ADJINC)/1000000.0', 'h2024')
    inc23 = stat('MAX(ADJINC)/1000000.0', 'h2023')
    hsg = stat('MAX(ADJHSG)/1000000.0', 'h2024')
    a = {}
    a[1] = stat('COUNT(*)')
    a[2] = stat('COUNT(*)', where='AGEP>=65')
    a[3] = stat('COUNT(*)', 'h2024', 'TYPEHUGQ=1')
    a[4] = stat('COUNT(*)', where='SEX=2')
    a[5] = stat('COUNT(*)', where='ESR=3')
    a[6] = stat('COUNT(*)', 'h2024', 'TYPEHUGQ=1 AND NP=0')
    a[7] = stat('SUM(PWGTP)', where='AGEP>=65')
    a[8] = stat('SUM(WGTP)', 'h2024', rent)
    a[9] = stat('SUM(AGEP*PWGTP)*1.0/SUM(PWGTP)')
    a[10] = stat('SUM(WAGP*ADJINC/1000000.0*PWGTP)/SUM(PWGTP)', where=emp)
    a[11] = median('AGEP', 'PWGTP', 'p2024')
    a[12] = median('WAGP','PWGTP','p2024',emp+' AND WAGP>0')*inc
    a[13] = median('HINCP','WGTP','h2024',occ)*inc
    a[14] = median('AGEP','PWGTP','p2024',fraction=.75)
    a[15] = stat('SUM(NP*WGTP)*1.0/SUM(WGTP)','h2024',occ)
    a[16] = stat('100.0*SUM(CASE WHEN AGEP<18 THEN PWGTP ELSE 0 END)/SUM(PWGTP)')
    a[17] = stat('100.0*SUM(CASE WHEN SCHL>=21 THEN PWGTP ELSE 0 END)/SUM(PWGTP)',where=adult)
    a[18] = stat('SUM(PWGTP)',join,rent)
    a[19] = median('HINCP','PWGTP',join,occ)*inc
    a[20] = stat('SUM(NP*PWGTP)*1.0/SUM(PWGTP)',join,occ)
    a[21] = stat('SUM(WGTP)',heads,hh_occ+' AND SEX=2')
    a[22] = median('AGEP','WGTP',heads,hh_occ)
    a[23] = stat('SUM(WGTP)','h2024 h',occ+' AND EXISTS (SELECT 1 FROM p2024 p WHERE p.SERIALNO=h.SERIALNO AND p.AGEP>=65)')
    a[24] = stat('SUM(PWGTP)',join,'TYPEHUGQ IN (2,3)')
    a[25] = stat('100.0*SUM(CASE WHEN TEN IN (1,2) THEN PWGTP ELSE 0 END)/SUM(PWGTP)',join,occ)
    a[26] = median('HINCP','WGTP',heads,hh_occ+' AND AGEP>=65')*inc
    a[27] = median('GRNTP','WGTP','h2024',occ+' AND GRNTP IS NOT NULL')*hsg
    a[28] = median('VALP','WGTP','h2024',occ+' AND TEN IN (1,2) AND VALP IS NOT NULL')*hsg
    a[29] = median('AGEP','PWGTP','p2023')
    a[30] = stat('SUM(PWGTP)')-stat('SUM(PWGTP)','p2023')
    a[31] = median('HINCP','WGTP','h2023',occ)*inc23
    a[32] = 100*(a[13]-a[31])/a[31]
    a[33] = a[8]-stat('SUM(WGTP)','h2023',rent)
    reps = {n: [] for n in range(34,39)}
    for r in range(1,81):
        pw, hw = f'PWGTP{r}', f'WGTP{r}'
        reps[34].append(stat(f'SUM({pw})',where='AGEP>=65'))
        reps[35].append(stat(f'SUM({hw})','h2024',rent))
        reps[36].append(stat(f'SUM(WAGP*ADJINC/1000000.0*{pw})/SUM({pw})',where=emp))
        reps[37].append(median('HINCP',hw,'h2024',occ)*inc)
        reps[38].append(stat(f'100.0*SUM(CASE WHEN SCHL>=21 THEN {pw} ELSE 0 END)/SUM({pw})',where=adult))
    for n, full in [(34,7),(35,8),(36,10),(37,13),(38,17)]:
        a[n] = math.sqrt(sum((x-a[full])**2 for x in reps[n])/20)
    with (args.results_dir/'submission.csv').open(newline='',encoding='utf-8') as f:
        submitted = {r['question_id']:r['answer'] for r in csv.DictReader(f)}
    from decimal import Decimal, ROUND_HALF_UP
    rows = []
    for n in range(1,39):
        digits = 2 if n in (9,15,20,38) else 1 if n in (16,17,25,32) else 0
        value = Decimal(str(a[n])).quantize(Decimal(1).scaleb(-digits),rounding=ROUND_HALF_UP)
        answer = f'{value:.{digits}f}'
        q = f'q{n:03d}'
        assert answer == submitted[q], (q,answer,submitted[q])
        rows.append({'question_id':q,'sql_answer':answer,'match':True})
    (args.results_dir/'validation.json').write_text(json.dumps({'all_38_match':True,'method':'Independent SQLite calculations','questions':rows},indent=2),encoding='utf-8')
    print('PASS: all 38 SQL answers exactly match submission.csv',flush=True)


if __name__ == '__main__':
    main()
