"""Reproducible in-memory ranking benchmark, including a separate buffer-build comparison."""
from pathlib import Path
import sys,random,time,statistics,json,platform,subprocess
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'python'))
from ranking import normalize,PythonIndex,NativeIndex

def measure(fn,repeats=7):
    fn();times=[]
    for _ in range(repeats):
        start=time.perf_counter();fn();times.append((time.perf_counter()-start)*1000)
    return round(statistics.median(times),4)
def main():
    rng=random.Random(2027);results=[]
    for n in (1000,5000,10000):
        d=48;k=10;matrix=[normalize([rng.random() for _ in range(d)]) for _ in range(n)];ids=list(range(1,n+1));query=normalize([rng.random() for _ in range(d)])
        py=PythonIndex(matrix,ids);native=NativeIndex(matrix,ids)
        a=py.query(query,k);b=native.query(query,k)
        assert [i for i,s in a]==[i for i,s in b]
        assert all(abs(x-y)<1e-12 for (_,x),(_,y) in zip(a,b))
        pm=measure(lambda:py.query(query,k));cm=measure(lambda:native.query(query,k))
        pe=measure(lambda:PythonIndex(matrix,ids).query(query,k));ce=measure(lambda:NativeIndex(matrix,ids).query(query,k))
        results.append({'items':n,'dimensions':d,'k':k,'repeats':7,'python_prepared_median_ms':pm,'c_prepared_median_ms':cm,'prepared_speedup':round(pm/cm,2),'python_build_and_query_ms':pe,'c_build_and_query_ms':ce,'build_and_query_speedup':round(pe/ce,2),'ranking_equivalent':True})
    report={'seed':2027,'machine':platform.platform(),'processor':platform.machine(),'python':sys.version.split()[0],'compiler':subprocess.run(['cc','--version'],text=True,capture_output=True).stdout.splitlines()[0],'flags':'-O3; no fast-math','scope':'In-memory dense normalized-vector cosine plus bounded top-k. Prepared excludes index validation/buffer construction for BOTH engines; C query includes ctypes call and result conversion. Build+query includes index validation and C buffer packing/library loading. Excludes Java, Python process startup, SQLite, TF-IDF, network, JSON and rendering. Synthetic dense data; not production API latency.','results':results}
    (ROOT/'reports/benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# Ranking benchmark','',report['scope'],'',f"Machine: {report['machine']} / {report['processor']}; Python {report['python']}; {report['compiler']}. Seven repeats after one warmup; median. Seed 2027.",'','| Items × dimensions | Python prepared (ms) | C prepared (ms) | Prepared speedup | Python build+query (ms) | C build+query (ms) | Build+query speedup |','|---|---:|---:|---:|---:|---:|---:|']
    for r in results:lines.append(f"| {r['items']} × {r['dimensions']} | {r['python_prepared_median_ms']} | {r['c_prepared_median_ms']} | {r['prepared_speedup']}× | {r['python_build_and_query_ms']} | {r['c_build_and_query_ms']} | {r['build_and_query_speedup']}× |")
    lines+=['','IDs and scores matched within 1e-12 for every benchmark case. No universal performance claim: packing can outweigh the C kernel savings. Re-run on the machine and workload you describe.']
    (ROOT/'reports/BENCHMARK.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
