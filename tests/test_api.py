"""Real HTTP integration across Java → Python → C, using an isolated temporary DB."""
import unittest,subprocess,sys,tempfile,os,socket,time,json
from pathlib import Path
from urllib.request import urlopen,Request
from urllib.error import HTTPError,URLError
ROOT=Path(__file__).resolve().parents[1]
class RestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.base=f'http://127.0.0.1:{cls.port}'
        cls.log=open(Path(cls.tmp.name)/'java.log','w+')
        cls.process=subprocess.Popen(['java','--add-modules','jdk.httpserver','-cp',str(ROOT/'build'),'RecommendationServer',str(ROOT),sys.executable,str(cls.port)],env=dict(os.environ,PINPOINT_DB=str(Path(cls.tmp.name)/'events.db')),stdout=cls.log,stderr=cls.log)
        for _ in range(100):
            try:urlopen(cls.base+'/api/health',timeout=1).close();break
            except (OSError,URLError):
                if cls.process.poll() is not None:raise RuntimeError('Java server exited during startup')
                time.sleep(.05)
        else:raise RuntimeError('Java API did not become ready')
    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.wait(timeout=10);cls.log.close();cls.tmp.cleanup()
    def get(self,path):
        with urlopen(self.base+path,timeout=10) as response:return json.load(response)
    def event(self,user,item,method='POST'):
        request=Request(self.base+'/api/likes',data=f'user={user}&item={item}'.encode(),method=method)
        with urlopen(request,timeout=10) as response:return json.load(response)
    def test_health_and_catalog(self):
        self.assertEqual(self.get('/api/health')['status'],'ok');self.assertEqual(len(self.get('/api/items')['items']),48)
    def test_like_recommend_unlike_end_to_end(self):
        self.event('api-demo',9);self.event('api-demo',9)
        native=self.get('/api/recommendations?user=api-demo&engine=c&k=5')
        pure=self.get('/api/recommendations?user=api-demo&engine=python&k=5')
        self.assertEqual(native['results'],pure['results']);self.assertEqual(native['liked_ids'],[9])
        self.assertEqual(native['mode'],'personalized');self.assertNotIn(9,[i['id'] for i in native['results']])
        self.event('api-demo',9,'DELETE');self.assertEqual(self.get('/api/recommendations?user=api-demo')['mode'],'cold_start')
    def test_invalid_parameters(self):
        for path in ['/api/recommendations?k=999','/api/recommendations?engine=bad','/api/items?user=a%27','/api/items?user=a&user=b']:
            with self.assertRaises(HTTPError) as caught:self.get(path)
            self.assertEqual(caught.exception.code,400)
    def test_unknown_item(self):
        with self.assertRaises(HTTPError) as caught:self.event('api-demo',9999)
        self.assertEqual(caught.exception.code,404)
    def test_bad_origin_rejected(self):
        request=Request(self.base+'/api/likes',data=b'user=demo&item=1',headers={'Origin':'https://example.com'})
        with self.assertRaises(HTTPError) as caught:urlopen(request)
        self.assertEqual(caught.exception.code,403)
    def test_bundled_photo(self):
        with urlopen(self.base+'/images/design-0.jpg') as response:
            self.assertEqual(response.headers['Content-Type'],'image/jpeg');self.assertTrue(response.read().startswith(b'\xff\xd8'))
    def test_static_demo_and_missing_route(self):
        with urlopen(self.base) as response:self.assertIn('PinPoint',response.read().decode())
        with self.assertRaises(HTTPError) as caught:self.get('/not-found')
        self.assertEqual(caught.exception.code,404)
if __name__=='__main__':unittest.main()
