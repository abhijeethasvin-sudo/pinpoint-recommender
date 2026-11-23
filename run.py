from pathlib import Path
import subprocess,sys,argparse
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8080);args=p.parse_args()
if not (ROOT/'build/RecommendationServer.class').exists():raise SystemExit('Run python3 build.py first.')
try:subprocess.run(['java','--add-modules','jdk.httpserver','-cp',str(ROOT/'build'),'RecommendationServer',str(ROOT),sys.executable,str(args.port)],check=True)
except KeyboardInterrupt:pass
