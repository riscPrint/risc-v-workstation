/* Narrow flat C2/1 reader. Any unsupported syntax returns -1 so that the
 * shared Python C2 validator can handle it. It never accepts unknown fields. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
typedef struct { int64_t src0, src1, dest, latency, kind, miss; } Op;
typedef int (*Decode)(uint32_t, int, Op*, uint64_t*);
static const char *keys[] = {"pc","pc_next","insn","rs1_rdata","rs2_rdata","rd_wdata","mem_addr","mem_rdata","mem_wdata", "order","cycle","mode","rs1","rs2","rd","mem_rmask","mem_wmask", "trap","intr","halt","mem_fault", "event","status"};
static const unsigned key_lengths[] = {2,7,4,9,9,8,8,9,9,5,5,4,3,3,2,9,9,4,4,4,9,5,6};
static void ws(const char **p, const char *end) { while (*p<end && (**p==' ' || **p=='\t' || **p=='\r'))++*p; }
static int literal(const char **p, const char *end, const char *v) {
 size_t n=strlen(v); if((size_t)(end-*p)<n || memcmp(*p,v,n))return 0; *p+=n;return 1;
}
static int number(const char **p, const char *end, int hex, uint64_t *v) {
 *v=0; int digits=0;
 if(hex && !literal(p,end,"\"0x"))return 0;
 while(*p<end) {
  char ch=**p; int d=ch>='0' && ch<='9'?ch-'0':hex && ch>='a' && ch<='f'?ch-'a'+10:-1;
  if(d<0)break;
  if(!hex && digits==1 && *v==0)return 0;
  unsigned base=hex?16:10;
  if(*v>(UINT64_MAX-(unsigned)d)/base)return 0;
  *v=*v*base+(unsigned)d;digits++;++*p;
 }
 return digits && (!hex || literal(p,end,"\""));
}
/* Cache decoder results. This does not cache dynamic operands or branch outcomes. */
typedef struct { uint32_t word; int rd, valid; Op op; uint64_t length, bk; } Template;
int64_t rvw_ooo_parse_c2(const char *p, size_t bytes, int xlen, Op *ops, uint64_t *info, int64_t capacity, Decode decode) {
 const char *end=p+bytes;
 const char *header_end=memchr(p,'\n',bytes); if(!header_end)return -1; p=header_end+1;
 int64_t n=0; uint64_t last_cycle=0; int ended=0;
 int key_order[23];for(int i=0;i<23;i++)key_order[i]=-1;
 Template *cache=calloc(65536,sizeof(Template)); if(!cache)return -1;
 #define FAIL do { free(cache); return -1; } while(0)
 while(p<end) {
  const char *e=memchr(p,'\n',(size_t)(end-p)); if(!e)e=end;
  uint64_t v[23]={0}, seen=0; ws(&p,e); if(ended || !literal(&p,e,"{"))FAIL;
  int field=0;
  for(;;) {
   ws(&p,e); if(!literal(&p,e,"\""))FAIL;
   const char *k=p; int index=field<23?key_order[field]:-1;
   size_t len=index>=0?key_lengths[index]:0;
   if(index>=0 && (size_t)(e-p)>len && p[len]=='\"' && !memcmp(p,keys[index],len))p+=len;
   else {
   uint32_t hash=2166136261u;
   while(p<e && *p!='\"'){hash=(hash^(unsigned char)*p)*16777619u;p++;}
   if(p==e)FAIL;
   len=(size_t)(p-k);index=-1;
   switch(hash){
    case 1313756516u: index=0;break;
    case 3418807436u: index=1;break;
    case 815396731u: index=2;break;
    case 4071299400u: index=3;break;
    case 2195842221u: index=4;break;
    case 3071207657u: index=5;break;
    case 2140026092u: index=6;break;
    case 4127691995u: index=7;break;
    case 615534356u: index=8;break;
    case 1932267671u: index=9;break;
    case 2663842801u: index=10;break;
    case 3966689298u: index=11;break;
    case 4057726873u: index=12;break;
    case 4007394016u: index=13;break;
    case 1498707683u: index=14;break;
    case 3905436167u: index=15;break;
    case 765559996u: index=16;break;
    case 1619038978u: index=17;break;
    case 714186564u: index=18;break;
    case 3904824570u: index=19;break;
    case 2953702597u: index=20;break;
    case 4264611999u: index=21;break;
    case 3125508079u: index=22;break;
   }
   if(index<0 || key_lengths[index]!=len || memcmp(k,keys[index],len))FAIL;
   }
   if(field<23)key_order[field]=index;field++;
   if(index<0 || (seen&(1ULL<<index)))FAIL;
   seen|=1ULL<<index;p++;ws(&p,e);if(!literal(&p,e,":"))FAIL;ws(&p,e);
   if(index<17) { if(!number(&p,e,index<9,&v[index]))FAIL; }
   else if(index<21) { if(literal(&p,e,"false"))v[index]=0;else if(literal(&p,e,"true"))v[index]=1;else FAIL; }
   else if(index==21) { if(!literal(&p,e,"\"end\""))FAIL; }
   else { if(!literal(&p,e,"\"pass\""))FAIL; }
   ws(&p,e);if(literal(&p,e,"}"))break;if(!literal(&p,e,","))FAIL;
  }
  ws(&p,e);if(p!=e)FAIL;p=e<end?e+1:e;
  if(!(seen&(1ULL<<10)) || v[10]<last_cycle || v[10]>INT64_MAX)FAIL;
  last_cycle=v[10];
  if(seen&(1ULL<<21)) { if(seen!=((1ULL<<10)|(1ULL<<21)|(1ULL<<22)))FAIL;ended=1;continue; }
  if(seen!=((1ULL<<21)-1) || n>=capacity || v[9]!=(uint64_t)n)FAIL;
  if(v[11]!=0 && v[11]!=1 && v[11]!=3)FAIL;
  for(int i=12;i<15;i++)if(v[i]>31)FAIL;
  for(int i=15;i<17;i++)if(v[i]>=(1ULL<<(xlen/8)))FAIL;
  for(int i=17;i<21;i++)if(v[i])FAIL;
  for(int i=0;i<9;i++)if((i==2 && v[i]>UINT32_MAX) || (xlen==32 && v[i]>UINT32_MAX))FAIL;
  uint64_t mask=v[15]?v[15]:v[16],offset=0;
  if(mask) { while(!(mask&1)){mask>>=1;offset++;} }
  if(mask&(mask+1))FAIL;
  if(v[6]>UINT64_MAX-offset)FAIL;
  uint64_t address=v[6]+offset;
  unsigned ix=((uint32_t)v[2]*2654435761u+(unsigned)v[14])&65535;
  Template *t=&cache[ix];
  if(!t->valid || t->word!=(uint32_t)v[2] || t->rd!=(int)v[14]) {
   uint64_t meta[2];
   if(decode((uint32_t)v[2],(int)v[14],&t->op,meta))FAIL;
   t->word=(uint32_t)v[2];t->rd=(int)v[14];t->length=meta[0];t->bk=meta[1];t->valid=1;
  }
  if(v[0]>UINT64_MAX-t->length)FAIL;
  ops[n]=t->op;ops[n].miss=v[1]!=v[0]+t->length;
  uint64_t size=0;while(mask){size++;mask>>=1;}
  if((ops[n].kind==3 || ops[n].kind==4) && (!size || address>UINT64_MAX-size || (xlen==32 && address+size>(1ULL<<32))))FAIL;
  uint64_t *a=info+6*n;a[0]=v[0];a[1]=v[1];a[2]=t->length;a[3]=address;a[4]=size;a[5]=t->bk;
  n++;
 }
 free(cache);return ended && n?n:-1;
}
