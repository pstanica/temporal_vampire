#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,collections,json
ap=argparse.ArgumentParser();ap.add_argument('csv_files',nargs='+');ap.add_argument('--out',default='summary.txt');a=ap.parse_args()
lines=[]
for fn in a.csv_files:
 rows=list(csv.DictReader(open(fn,encoding='utf-8')));lines.append(f'FILE: {fn}');groups=collections.defaultdict(collections.Counter)
 for r in rows:groups[(r.get('prover','portfolio'),r.get('theory_name',r.get('winner','portfolio')),r.get('seed_mode',''))][r.get('status',r.get('final_status',''))]+=1
 for k,c in sorted(groups.items()):lines.append(f'  {k}: '+', '.join(f'{s}={n}' for s,n in sorted(c.items())))
 lines.append('')
Path(a.out).write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
