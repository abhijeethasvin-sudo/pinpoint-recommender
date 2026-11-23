"""Equivalent Python/C cosine top-k implementations with a documented ctypes boundary."""
import ctypes, heapq, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def normalize(values):
    norm=math.sqrt(sum(v*v for v in values))
    return [v/norm for v in values] if norm else [0.0]*len(values)
def validate(matrix,query,ids,k):
    if len(matrix)!=len(ids) or len(set(ids))!=len(ids):raise ValueError('Unique ID required for each row')
    if not isinstance(k,int) or not 0<=k<=100000:raise ValueError('Invalid k')
    if not query or any(len(row)!=len(query) for row in matrix):raise ValueError('Invalid vector dimensions')
    if any(not isinstance(i,int) or not 0<i<2**31 for i in ids):raise ValueError('IDs must be positive int32 values')
    if not all(math.isfinite(v) for row in [query,*matrix] for v in row):raise ValueError('Non-finite vector')
class PythonIndex:
    def __init__(self,matrix,ids):
        self.matrix=matrix;self.ids=ids;self.d=len(matrix[0]) if matrix else 0
        if matrix:validate(matrix,[0.0]*self.d,ids,0)
        elif ids:raise ValueError('Rows and IDs differ')
    def query(self,query,k):
        if not isinstance(k,int) or not 0<=k<=100000:raise ValueError('Invalid k')
        if self.matrix and len(query)!=self.d:raise ValueError('Invalid dimensions')
        if not all(math.isfinite(v) for v in query):raise ValueError('Non-finite query')
        scores=((ident,sum(a*b for a,b in zip(row,query))) for ident,row in zip(self.ids,self.matrix))
        return heapq.nsmallest(k,scores,key=lambda m:(-m[1],m[0]))
def python_topk(matrix,query,ids,k):
    validate(matrix,query,ids,k)
    return PythonIndex(matrix,ids).query(query,k)
class NativeIndex:
    """Prepare buffers once, then reuse them for multiple queries."""
    def __init__(self,matrix,ids):
        self.n=len(matrix);self.d=len(matrix[0]) if matrix else 0
        if matrix:validate(matrix,[0.0]*self.d,ids,0)
        elif ids:raise ValueError('Rows and IDs differ')
        self.matrix=(ctypes.c_double*(self.n*self.d))(*(v for row in matrix for v in row))
        self.ids=(ctypes.c_int*self.n)(*ids)
        suffix='dylib' if sys.platform=='darwin' else 'so'
        self.lib=ctypes.CDLL(str(ROOT/f'build/libtopk.{suffix}'))
        self.fn=self.lib.rank_topk
        self.fn.argtypes=[ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_int),ctypes.c_size_t,ctypes.c_size_t,ctypes.c_size_t,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_double)]
        self.fn.restype=ctypes.c_int
    def query(self,query,k):
        if not isinstance(k,int) or not 0<=k<=100000:raise ValueError('Invalid k')
        if self.n and len(query)!=self.d:raise ValueError('Invalid query dimensions')
        if not all(math.isfinite(v) for v in query):raise ValueError('Non-finite query')
        k=min(k,self.n)
        if not k:return []
        q=(ctypes.c_double*len(query))(*query);out=(ctypes.c_int*k)();scores=(ctypes.c_double*k)()
        size=self.fn(self.matrix,q,self.ids,self.n,self.d,k,out,scores)
        if size<0:raise RuntimeError('Native ranking rejected input')
        return [(out[i],scores[i]) for i in range(size)]
def c_topk(matrix,query,ids,k):
    validate(matrix,query,ids,k)
    return NativeIndex(matrix,ids).query(query,k)
