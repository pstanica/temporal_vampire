#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,collections,statistics
ap=argparse.ArgumentParser();ap.add_argument('results_csv');ap.add_argument('--out');a=ap.parse_args()
rows=list(csv.DictReader(open(a.results_csv,encoding='utf-8')))
by=collections.defaultdict(list)
for r in rows:by[r['theory_name']].append(r)
lines=[]
solved={}
for th,rs in sorted(by.items()):
    c=collections.Counter(r['status'] for r in rs); ss={r['conjecture'] for r in rs if r['status']=='THEOREM'}; solved[th]=ss
    ts=[float(r['seconds']) for r in rs if r['status']=='THEOREM']
    med=statistics.median(ts) if ts else float('nan')
    lines.append(f'{th}: THEOREM={len(ss)} / {len(rs)}; statuses={dict(sorted(c.items()))}; median_theorem_s={med:.6f}')
if solved:
    union=set().union(*solved.values()); inter=set.intersection(*solved.values()) if len(solved)>1 else next(iter(solved.values()))
    lines.append(f'UNION_THEOREMS={len(union)}')
    lines.append(f'INTERSECTION_THEOREMS={len(inter)}')
    for th,ss in sorted(solved.items()):
        other=set().union(*(v for k,v in solved.items() if k!=th)) if len(solved)>1 else set()
        lines.append(f'UNIQUE_{th}={len(ss-other)}')
text='\n'.join(lines)+'\n';print(text,end='')
if a.out:Path(a.out).write_text(text)
