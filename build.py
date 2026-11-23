"""Portable macOS/Linux build; no package downloads or third-party Java dependencies."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parent
(ROOT/'build').mkdir(exist_ok=True)
suffix='dylib' if sys.platform=='darwin' else 'so'
subprocess.run(['cc','-std=c11','-O3','-Wall','-Wextra','-Werror','-fPIC','-shared',str(ROOT/'native/topk.c'),'-o',str(ROOT/f'build/libtopk.{suffix}')],check=True)
subprocess.run(['javac','--release','17','--add-modules','jdk.httpserver','-d',str(ROOT/'build'),str(ROOT/'java/RecommendationServer.java')],check=True)
print('Built native C library and Java REST server.')
