"""Post-hoc analysis only: no re-run or new token savings measurement."""
import json
from pathlib import Path
from src.decision_gate import decide
from src.metrics import verdict_accuracy

root = Path(__file__).parent
truth = {c['name']:c['ground_truth']['verdict'] for c in json.loads((root/'data/candidates.json').read_text())}
out = {'status':'post_hoc_development_analysis', 'prospective_validation':False, 'modes':{}}
for mode in ('baseline','meko'):
    original=json.loads((root/f'results/reports-{mode}.json').read_text())
    derived=[]
    for r in original:
        gate=decide(r.get('agents',{}).get('scout',{}))
        derived.append({'candidate':r['candidate'],'run':r['run'],'original_verdict':r['verdict'],**gate})
    out['modes'][mode]={'accuracy':verdict_accuracy(derived,truth),'reports':derived}
(root/'results/post-hoc-gate.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({m:d['accuracy'] for m,d in out['modes'].items()},indent=2))
