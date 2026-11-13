/* Integer RV32/64 IMC templates for whole-file C2 packing. Other classes fall back. */
#include <stdint.h>
#include <stddef.h>
typedef struct { int64_t src0,src1,dest,latency,kind,miss; } Op;
int rvw_ooo_decode_integer(uint32_t word,int rd,int xlen,const int64_t* latencies,int branch,Op* out,uint64_t* meta) {
 if(xlen!=32 && xlen!=64)return -1;
 unsigned length=(word&3)==3?4:2;
 unsigned a=0,b=0,kind=0,bk=0;
 if(length==4) {
  unsigned op=word&127,f3=(word>>12)&7,f7=word>>25;
  unsigned r1=(word>>15)&31,r2=(word>>20)&31;
  switch(op) {
   case 0x33:case 0x3b:
    if(op==0x3b && xlen!=64)return -1;
    if(f7==1) { if(op==0x3b && f3>0 && f3<4)return -1;kind=f3<4?1:2; }
    else if(f7==0) { if(op==0x3b && f3!=0 && f3!=1 && f3!=5)return -1; }
    else if(f7==32) { if(f3!=0 && f3!=5)return -1; }
    else return -1;
    a=r1;b=r2;break;
   case 0x13:case 0x1b: {
    int wide=op==0x1b;
    if(wide && (xlen!=64 || (f3!=0 && f3!=1 && f3!=5)))return -1;
    if(f3==1 || f3==5) {
     unsigned upper=word>>((wide || xlen==32)?25:26);
     if(upper!=0 && !(f3==5 && upper==((wide || xlen==32)?32:16)))return -1;
    }
    a=r1;break;
   }
   case 0x37:case 0x17:break;
   case 0x03:
    if(f3==7 || (xlen==32 && (f3==3 || f3==6)))return -1;
    a=r1;kind=3;break;
   case 0x23:
    if(f3>3 || (xlen==32 && f3==3))return -1;
    a=r1;b=r2;kind=4;break;
   case 0x63:
    if(f3==2 || f3==3)return -1;
    a=r1;b=r2;kind=5;bk=1;break;
   case 0x6f:kind=6;bk=(rd==1 || rd==5)?4:2;break;
   case 0x67:
    if(f3)return -1;
    a=r1;kind=6;bk=(rd==1 || rd==5)?5:(r1==1 || r1==5)?6:3;break;
   default:return -1;
  }
 } else {
  word&=65535;
  unsigned q=word&3,f=(word>>13)&7,r=(word>>7)&31,s=(word>>2)&31;
  unsigned rc=8+((word>>7)&7),sc=8+((word>>2)&7);
  if(q==0) {
   if(f==0) { if(!((word>>5)&255))return -1;a=2; }
   else if(f==2 || (f==3 && xlen==64)) { a=rc;kind=3; }
   else if(f==6 || (f==7 && xlen==64)) { a=rc;b=sc;kind=4; }
   else return -1;
  } else if(q==1) {
   if(f==0)a=r;
   else if(f==1) { if(xlen==32){kind=6;bk=4;}else{if(!r)return -1;a=r;} }
   else if(f==2)a=0;
   else if(f==3) { if(!(((word>>7)&32)|((word>>2)&31)))return -1;if(r==2)a=2; }
   else if(f==4) {
    unsigned sub=(word>>10)&3;
    a=rc;
    if(sub<3) { if(sub<2 && xlen==32 && (word&4096))return -1; }
    else {
     if((word&4096) && (xlen!=64 || ((word>>5)&3)>1))return -1;
     b=sc;
    }
   } else if(f==5) { kind=6;bk=(rd==1 || rd==5)?4:2; }
   else { a=rc;kind=5;bk=1; }
  } else if(q==2) {
   if(f==0) { if(xlen==32 && (word&4096))return -1;a=r; }
   else if(f==2 || (f==3 && xlen==64)) { if(!r)return -1;a=2;kind=3; }
   else if(f==4) {
    if(s) { a=(word&4096)?r:0;b=s; }
    else {
     if(!r)return -1;
     a=r;kind=6;bk=((word&4096) || rd==1 || rd==5)?5:(r==1 || r==5)?6:3;
    }
   } else if(f==6 || (f==7 && xlen==64)) { a=2;b=s;kind=4; }
   else return -1;
  } else return -1;
 }
 if(latencies[kind]<1)return -1;
 *out=(Op){a,b,rd,latencies[kind],kind,0};meta[0]=length;meta[1]=branch?bk:0;
 return 0;
}

typedef int (*Decode)(uint32_t,int,Op*,uint64_t*);
extern int64_t rvw_ooo_parse_c2(const char*,size_t,int,Op*,uint64_t*,int64_t,Decode);
static _Thread_local struct { int xlen,branch; const int64_t* latencies; } context;
static int template(uint32_t word,int rd,Op* out,uint64_t* meta) {
 return rvw_ooo_decode_integer(word,rd,context.xlen,context.latencies,context.branch,out,meta);
}
int64_t rvw_ooo_parse_c2_native(const char* data,size_t bytes,int xlen,Op* ops,uint64_t* info,int64_t capacity,const int64_t* latencies,int branch) {
 context.xlen=xlen;context.branch=branch;context.latencies=latencies;
 return rvw_ooo_parse_c2(data,bytes,xlen,ops,info,capacity,template);
}
