/* Dense normalized-vector cosine ranking with a bounded worst-first heap.
 * ABI: caller owns contiguous arrays; returns number of results or -1. */
#include <stddef.h>
#include <stdlib.h>
#include <math.h>
#include <stdint.h>
typedef struct {int id; double score;} Match;
static int better(Match a,Match b) {return a.score>b.score || (a.score==b.score && a.id<b.id);}
static void swap(Match *a,Match *b) {Match t=*a;*a=*b;*b=t;}
static void sink(Match *heap,size_t count,size_t root) {
    for(;;) {size_t worst=root,left=root*2+1,right=left+1;
        if(left<count && better(heap[worst],heap[left])) worst=left;
        if(right<count && better(heap[worst],heap[right])) worst=right;
        if(worst==root) break;
        swap(&heap[root],&heap[worst]);root=worst;
    }
}
static int compare(const void *aa,const void *bb) {
    Match a=*(const Match*)aa,b=*(const Match*)bb;
    return better(a,b)?-1:better(b,a)?1:0;
}
int rank_topk(const double *matrix,const double *query,const int *ids,
              size_t n,size_t d,size_t k,int *out_ids,double *out_scores) {
    if(k==0 || n==0) return 0;
    if(!matrix||!query||!ids||!out_ids||!out_scores||d==0||n>SIZE_MAX/d) return -1;
    if(k>n) k=n;
    if(k>SIZE_MAX/sizeof(Match)) return -1;
    Match *heap=malloc(k*sizeof(Match));if(!heap) return -1;
    for(size_t j=0;j<d;j++) if(!isfinite(query[j])) {free(heap);return -1;}
    size_t count=0;
    for(size_t i=0;i<n;i++) {
        double score=0;
        for(size_t j=0;j<d;j++) score+=matrix[i*d+j]*query[j];
        if(!isfinite(score)) {free(heap);return -1;}
        Match m={ids[i],score};
        if(count<k) {
            size_t at=count++;heap[at]=m;
            while(at>0) {size_t parent=(at-1)/2;if(!better(heap[parent],heap[at])) break;swap(&heap[parent],&heap[at]);at=parent;}
        } else if(better(m,heap[0])) {heap[0]=m;sink(heap,count,0);}
    }
    qsort(heap,count,sizeof(Match),compare);
    for(size_t i=0;i<count;i++) {out_ids[i]=heap[i].id;out_scores[i]=heap[i].score;}
    free(heap);return (int)count;
}
