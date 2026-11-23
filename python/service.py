"""Python data/personalization service, called by Java through a bounded subprocess."""
from pathlib import Path
import json,sqlite3,sys,os,re,time,math
from contextlib import contextmanager
from ranking import normalize,c_topk,python_topk
ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.environ.get('PINPOINT_DB',str(ROOT/'runtime/events.db')))
def catalog():return json.loads((ROOT/'data/items.json').read_text())
@contextmanager
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(DB,timeout=10)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS likes(user TEXT NOT NULL,item INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user,item))')
        with db:yield db
    finally:db.close()
def user_id(user):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',user):raise ValueError('User must be 1–40 letters, digits, underscores or hyphens')
    return user
def vectors(items):
    tags=sorted({t for i in items for t in i['tags']});lookup={t:n for n,t in enumerate(tags)}
    idf={t:math.log((1+len(items))/(1+sum(t in i['tags'] for i in items)))+1 for t in tags}
    matrix=[]
    for item in items:
        row=[0.0]*len(tags)
        for tag in item['tags']:row[lookup[tag]]=idf[tag]
        matrix.append(normalize(row))
    return tags,matrix
def liked(user):
    user_id(user)
    with connect() as db:return {row[0] for row in db.execute('SELECT item FROM likes WHERE user=?',(user,))}
def record_like(user,item,remove=False):
    user_id(user)
    if item not in {i['id'] for i in catalog()}:raise LookupError('Unknown item')
    with connect() as db:
        if remove:db.execute('DELETE FROM likes WHERE user=? AND item=?',(user,item))
        else:db.execute('INSERT OR IGNORE INTO likes(user,item) VALUES(?,?)',(user,item))
    return {'user':user,'item':item,'liked':not remove,'liked_ids':sorted(liked(user))}
def recommend(user,k=8,engine='c'):
    started=time.perf_counter();user_id(user)
    if not 1<=k<=50 or engine not in ('c','python'):raise ValueError('k must be 1–50 and engine c or python')
    items=catalog();tags,matrix=vectors(items);saved=liked(user);candidates=[(i,v) for i,v in zip(items,matrix) if i['id'] not in saved]
    if not saved:
        with connect() as db:counts=dict(db.execute('SELECT item,COUNT(*) FROM likes GROUP BY item'))
        ordered=sorted((i for i,v in candidates),key=lambda i:(-counts.get(i['id'],0),i['id']))[:k]
        results=[dict(i,score=None,reasons=['Popular across local demo profiles'] if counts.get(i['id'],0) else ['Explore to start your interest profile']) for i in ordered]
        mode='cold_start'
    else:
        profile=normalize([sum(v[j] for i,v in zip(items,matrix) if i['id'] in saved) for j in range(len(tags))])
        fn=c_topk if engine=='c' else python_topk
        scores=fn([v for i,v in candidates],profile,[i['id'] for i,v in candidates],k)
        by_id={i['id']:i for i in items};interests={t for i in items if i['id'] in saved for t in i['tags']}
        results=[dict(by_id[ident],score=round(score,8),reasons=sorted(interests.intersection(by_id[ident]['tags']))) for ident,score in scores]
        mode='personalized'
    return {'user':user,'engine':engine,'mode':mode,'liked_ids':sorted(saved),'results':results,'pipeline_ms':round((time.perf_counter()-started)*1000,3)}
def dispatch(args):
    if not args:raise ValueError('Missing operation')
    if args[0]=='items':
        user=args[1] if len(args)>1 else 'demo';return {'items':catalog(),'liked_ids':sorted(liked(user))}
    if args[0]=='recommend' and len(args)==5:
        if args[4]!='v1':raise ValueError('Invalid protocol')
        return recommend(args[1],int(args[2]),args[3])
    if args[0] in ('like','unlike') and len(args)==3:return record_like(args[1],int(args[2]),args[0]=='unlike')
    raise ValueError('Invalid operation')
if __name__=='__main__':
    try:print(json.dumps(dispatch(sys.argv[1:]),allow_nan=False))
    except LookupError as exc:print(json.dumps({'error':str(exc)}));sys.exit(3)
    except ValueError as exc:print(json.dumps({'error':str(exc)}));sys.exit(2)
    except Exception:
        import traceback;traceback.print_exc(file=sys.stderr);print(json.dumps({'error':'Pipeline unavailable; check server logs and native build'}));sys.exit(1)
