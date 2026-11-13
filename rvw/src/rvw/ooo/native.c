/* Integer-only reference schedule. Keep phase order identical to core.py. */
#include <stdint.h>
#include <stdlib.h>
typedef struct { int64_t src0, src1, dest, latency; } Op;
typedef struct { int64_t fetch_width, fetch_entries, rename_width, rob_entries,
 issue_width, issue_entries, commit_width, physical_registers, max_cycles; } Config;
typedef struct { int64_t cycles, issued, dependency_blocked, rob_full,
 issue_full, register_full, peak_rob, peak_issue, peak_fetch,
 retiring, frontend, backend; } Result;
int rvw_ooo_abi(void) { return 1; }
int rvw_ooo_run(int64_t n, const Op *ops, const Config *c, Result *r) {
 int64_t *done = malloc(sizeof(int64_t)*n), *d0 = malloc(sizeof(int64_t)*n),
 *d1 = malloc(sizeof(int64_t)*n);
 if (!done || !d0 || !d1) { free(done);free(d0);free(d1);return -1; }
 for (int64_t i=0;i<n;i++) done[i]=-1;
 int64_t writers[32];for(int i=0;i<32;i++)writers[i]=-1;
 int64_t fetched=0, renamed=0, retired=0, waiting=0, allocated=0;
 *r=(Result){0};
 for (int64_t cycle=0;cycle<c->max_cycles;cycle++) {
  int64_t committed=0;
  while (committed<c->commit_width && retired<renamed && done[retired]>=0 && done[retired]<=cycle) {
   allocated-=ops[retired].dest>0; retired++; committed++;
  }
  r->retiring+=committed;
  if(renamed>retired)r->backend+=c->commit_width-committed;
  else r->frontend+=c->commit_width-committed;
  if(retired==n){r->cycles=cycle+1;free(done);free(d0);free(d1);return 0;}
  int64_t issued=0, blocked=0;
  for(int64_t i=retired;i<renamed && issued<c->issue_width;i++) {
   if(done[i]>=0)continue;
   if((d0[i]>=0 && (done[d0[i]]<0 || done[d0[i]]>cycle)) ||
      (d1[i]>=0 && (done[d1[i]]<0 || done[d1[i]]>cycle))) {blocked=1;continue;}
   done[i]=cycle+ops[i].latency;issued++;waiting--;r->issued++;
  }
  r->dependency_blocked+=blocked;
  for(int64_t lane=0;lane<c->rename_width && renamed<fetched;lane++) {
   if(renamed-retired>=c->rob_entries){r->rob_full++;break;}
   if(waiting>=c->issue_entries){r->issue_full++;break;}
   if(ops[renamed].dest>0 && c->physical_registers && allocated>=c->physical_registers-32){r->register_full++;break;}
   d0[renamed]=ops[renamed].src0>0?writers[ops[renamed].src0]:-1;
   d1[renamed]=ops[renamed].src1>0?writers[ops[renamed].src1]:-1;
   if(ops[renamed].dest>0){writers[ops[renamed].dest]=renamed;allocated++;}
   waiting++;renamed++;
  }
  for(int64_t lane=0;lane<c->fetch_width && fetched<n && fetched-renamed<c->fetch_entries;lane++)fetched++;
  if(renamed-retired>r->peak_rob)r->peak_rob=renamed-retired;
  if(waiting>r->peak_issue)r->peak_issue=waiting;
  if(fetched-renamed>r->peak_fetch)r->peak_fetch=fetched-renamed;
 }
 free(done);free(d0);free(d1);return 1;
}
