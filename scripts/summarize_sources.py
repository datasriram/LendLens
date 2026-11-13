import csv, json
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with open(root/'config'/'direct_sources.csv',encoding='utf-8') as f: rows=list(csv.DictReader(f))
summary={
  'curated_direct_sources':len(rows),
  'publishers':Counter(r['publisher'] for r in rows),
  'categories':Counter(r['category'] for r in rows),
  'formats':Counter(r['source_format'] for r in rows),
  'temporal_roles':Counter(r['temporal_role'] for r in rows),
}
(root/'data'/'reports'/'source_catalog_summary.json').write_text(json.dumps(summary,default=dict,indent=2),encoding='utf-8')
print(json.dumps(summary,default=dict,indent=2))
