"""Held-out synthetic interactions; deliberately separate from live demo profiles."""
import sys,random,tempfile,json,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'python'))
import service

def main():
    rng=random.Random(2027);items=service.catalog();groups=collections.defaultdict(list)
    for item in items:groups[item['category']].append(item['id'])
    profiles=[];counts=collections.Counter()
    for category,ids in sorted(groups.items()):
        for n in range(6):
            sample=rng.sample(ids,4);train=sample[:2];test=set(sample[2:]);user=f'eval_{category}_{n}'
            profiles.append((user,train,test));counts.update(train)
    old=service.DB
    with tempfile.TemporaryDirectory() as tmp:
        service.DB=Path(tmp)/'evaluation.db'
        try:
            for user,train,test in profiles:
                for ident in train:service.record_like(user,ident)
            metrics={'personalized':[],'popularity':[]}
            for user,train,test in profiles:
                native=service.recommend(user,5,'c')['results'];pure=service.recommend(user,5,'python')['results'];assert native==pure
                predicted=[i['id'] for i in native]
                baseline=sorted((i['id'] for i in items if i['id'] not in train),key=lambda i:(-counts[i],i))[:5]
                for name,result in [('personalized',predicted),('popularity',baseline)]:
                    hits=len(set(result)&test);metrics[name].append({'precision_at_5':hits/5,'recall_at_5':hits/len(test),'hit_rate_at_5':float(hits>0)})
        finally:service.DB=old
    aggregate={name:{key:round(sum(r[key] for r in rows)/len(rows),4) for key in rows[0]} for name,rows in metrics.items()}
    report={'seed':2027,'profiles':len(profiles),'items':len(items),'train_likes_per_profile':2,'heldout_likes_per_profile':2,'k':5,'metrics':aggregate,'limits':'Synthetic category-based interactions generated from the same catalog tags. Held-out per-user feedback is excluded from profile construction and popularity counts, but relevance design favors content filtering. This validates the evaluation pipeline, not real-user quality or generalization. No live demo data is read or changed.'}
    (ROOT/'reports/evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    text='# Offline evaluation\n\n'+report['limits']+'\n\n36 profiles; 48 items; 2 training likes and 2 held-out likes per profile; k=5; seed 2027.\n\n| Method | Precision@5 | Recall@5 | Hit rate@5 |\n|---|---:|---:|---:|\n'
    for name,r in aggregate.items():text+=f"| {name} | {r['precision_at_5']} | {r['recall_at_5']} | {r['hit_rate_at_5']} |\n"
    text+='\nC and Python returned equivalent recommendations for every evaluation profile. Do not describe these synthetic results as production accuracy. Next step: evaluate on independently collected or licensed real interactions.\n'
    (ROOT/'reports/EVALUATION.md').write_text(text);print(text)
if __name__=='__main__':main()
