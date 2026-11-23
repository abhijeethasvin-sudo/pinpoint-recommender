import unittest,sys,tempfile,random,math,json,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
import service
from ranking import python_topk,c_topk,normalize,NativeIndex,PythonIndex
class Ranking(unittest.TestCase):
    def test_known_cosine_and_ties(self):
        rows=[[1.,0.],[0.,1.],[1.,0.]];ids=[9,2,1]
        self.assertEqual(c_topk(rows,[1.,0.],ids,3),[(1,1.),(9,1.),(2,0.)])
        self.assertEqual(c_topk(rows,[1.,0.],ids,3),python_topk(rows,[1.,0.],ids,3))
    def test_randomized_equivalence(self):
        r=random.Random(2027)
        for n in [1,7,51,250]:
            matrix=[normalize([r.uniform(-1,1) for _ in range(17)]) for _ in range(n)];query=normalize([r.uniform(-1,1) for _ in range(17)]);ids=list(range(n,0,-1))
            for k in [0,1,5,n+2]:
                a=c_topk(matrix,query,ids,k);b=python_topk(matrix,query,ids,k)
                self.assertEqual([i for i,s in a],[i for i,s in b])
                for (_,x),(_,y) in zip(a,b):self.assertAlmostEqual(x,y,places=12)
    def test_empty_candidates(self):self.assertEqual(c_topk([], [1.],[],3),[])
    def test_zero_query(self):self.assertEqual(c_topk([[1.],[2.]],[0.],[8,2],2),[(2,0.),(8,0.)])
    def test_invalid_dimensions(self):
        for fn in [c_topk,python_topk]:
            with self.assertRaises(ValueError):fn([[1.,2.]],[1.],[1],1)
    def test_invalid_numbers(self):
        for fn in [c_topk,python_topk]:
            with self.assertRaises(ValueError):fn([[math.nan]],[1.],[1],1)
    def test_duplicate_ids(self):
        with self.assertRaises(ValueError):c_topk([[1.],[2.]],[1.],[1,1],1)
    def test_negative_k(self):
        with self.assertRaises(ValueError):c_topk([[1.]],[1.],[1],-1)
    def test_native_rejects_nonfinite_direct_call(self):
        import ctypes
        index=NativeIndex([[1.]],[1]);q=(ctypes.c_double*1)(math.nan);out=(ctypes.c_int*1)();scores=(ctypes.c_double*1)()
        self.assertEqual(index.fn(index.matrix,q,index.ids,1,1,1,out,scores),-1)
class Personalization(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.old=service.DB;service.DB=Path(self.tmp.name)/'events.db'
    def tearDown(self):service.DB=self.old;self.tmp.cleanup()
    def test_cold_start(self):self.assertEqual(service.recommend('new')['mode'],'cold_start')
    def test_like_idempotent(self):
        service.record_like('demo',9);service.record_like('demo',9);self.assertEqual(service.liked('demo'),{9})
    def test_personalized_excludes_liked(self):
        service.record_like('demo',9);r=service.recommend('demo');self.assertEqual(r['mode'],'personalized');self.assertNotIn(9,[i['id'] for i in r['results']]);self.assertEqual(r['results'][0]['category'],'design')
    def test_c_python_service_equivalence(self):
        service.record_like('demo',9);service.record_like('demo',25)
        self.assertEqual(service.recommend('demo',8,'c')['results'],service.recommend('demo',8,'python')['results'])
    def test_unlike(self):
        service.record_like('demo',9);service.record_like('demo',9,True);self.assertEqual(service.liked('demo'),set())
    def test_user_isolation(self):
        service.record_like('a',1);service.record_like('b',9);self.assertEqual(service.liked('a'),{1});self.assertEqual(service.liked('b'),{9})
    def test_unknown_item(self):
        with self.assertRaises(LookupError):service.record_like('demo',9999)
    def test_bad_user(self):
        with self.assertRaises(ValueError):service.recommend("a';DROP TABLE likes")
    def test_popularity_fallback(self):
        service.record_like('a',20);service.record_like('b',20);self.assertEqual(service.recommend('new')['results'][0]['id'],20)
    def test_all_items_liked(self):
        for i in service.catalog():service.record_like('demo',i['id'])
        self.assertEqual(service.recommend('demo')['results'],[])
    def test_persists_across_processes(self):
        env=dict(os.environ,PINPOINT_DB=str(service.DB));result=subprocess.run([sys.executable,str(ROOT/'python/service.py'),'like','demo','9'],capture_output=True,text=True,check=True,env=env)
        self.assertTrue(json.loads(result.stdout)['liked']);self.assertEqual(service.liked('demo'),{9})
if __name__=='__main__':unittest.main()
