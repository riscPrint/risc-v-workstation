/* Committed-path scheduler. Keep phase order identical to core.py. */
#include <stdint.h>
#include <stdlib.h>
typedef struct { int64_t src0, src1, dest, latency, kind, miss; } Op;
typedef struct { int64_t fetch_width, fetch_entries, rename_width, rob_entries,
 issue_width, issue_entries, commit_width, physical_registers, max_cycles,
 load_entries, store_entries, branch_penalty, branch_speculation, ports[7]; } Config;
typedef struct { int64_t cycles, issued, dependency_blocked, rob_full,
 issue_full, register_full, peak_rob, peak_issue, peak_fetch,
 retiring, frontend, backend, bad_speculation, loads, stores, load_full,
 store_full, branches, branch_misses, wrong_path_fetch_slots_estimate,
 port_blocked, correct_path_speculative_issues; } Result;
int rvw_ooo_abi(void) { return 2; }
int rvw_ooo_run(int64_t n, const Op *ops, const Config *c, Result *r) {
 int64_t *done = malloc(sizeof(int64_t)*n), *d0 = malloc(sizeof(int64_t)*n),
 *d1 = malloc(sizeof(int64_t)*n);
 if (!done || !d0 || !d1) { free(done);free(d0);free(d1);return -1; }
 for (int64_t i=0;i<n;i++)done[i]=-1;
 int64_t writers[32];for(int i=0;i<32;i++)writers[i]=-1;
 int64_t fetched=0, renamed=0, retired=0, waiting=0, allocated=0;
 int64_t loads=0, stores=0, blocked_until=0, unresolved=-1;
 *r=(Result){0};
 for (int64_t cycle=0;cycle<c->max_cycles;cycle++) {
  int64_t committed=0;
  while (committed<c->commit_width && retired<renamed && done[retired]>=0 && done[retired]<=cycle) {
   allocated-=ops[retired].dest>0;
   loads-=ops[retired].kind==3; stores-=ops[retired].kind==4;
   retired++; committed++;
  }
  r->retiring+=committed;
  if(cycle<blocked_until)r->bad_speculation+=c->commit_width-committed;
  else if(renamed>retired)r->backend+=c->commit_width-committed;
  else r->frontend+=c->commit_width-committed;
  if(retired==n){r->cycles=cycle+1;free(done);free(d0);free(d1);return 0;}
  if(unresolved>=0 && done[unresolved]<=cycle)unresolved=-1;
  int64_t issued=0, blocked=0, ports[7]={0};
  int branch_hold=0, speculating=0, memory_hold=0;
  for(int64_t i=retired;i<renamed && issued<c->issue_width;i++) {
   if(done[i]>=0)goto scanned;
   if((d0[i]>=0 && (done[d0[i]]<0 || done[d0[i]]>cycle)) ||
      (d1[i]>=0 && (done[d1[i]]<0 || done[d1[i]]>cycle))) {blocked=1;goto scanned;}
   if(cycle<blocked_until || branch_hold)goto scanned;
   int64_t kind=ops[i].kind;
   if(ports[kind]>=c->ports[kind]){r->port_blocked++;goto scanned;}
   if((kind==3 || kind==4) && memory_hold)goto scanned;
   if(kind>=5) {
    r->branches++;
    if(ops[i].miss) {
     r->branch_misses++;
     int64_t until=cycle+ops[i].latency+c->branch_penalty;
     if(until>blocked_until)blocked_until=until;
     r->wrong_path_fetch_slots_estimate+=c->branch_penalty*c->fetch_width;
    }
    if(!c->branch_speculation || ops[i].miss)unresolved=i;
   }
   done[i]=cycle+ops[i].latency;issued++;waiting--;r->issued++;ports[kind]++;
   if(speculating)r->correct_path_speculative_issues++;
scanned:
   /* Prefix state includes earlier entries issued in this phase. It replaces
      repeated walks over older branches and memory operations. */
   if(done[i]<0 || done[i]>cycle) {
    if(ops[i].kind>=5) {
     if(c->branch_speculation && done[i]>=0 && !ops[i].miss)speculating=1;
     else branch_hold=1;
    }
    if(ops[i].kind==3 || ops[i].kind==4)memory_hold=1;
   }
  }
  r->dependency_blocked+=blocked;
  for(int64_t lane=0;lane<c->rename_width && renamed<fetched;lane++) {
   if(cycle<blocked_until || unresolved>=0)break;
   int64_t kind=ops[renamed].kind;
   if(renamed-retired>=c->rob_entries){r->rob_full++;break;}
   if(waiting>=c->issue_entries){r->issue_full++;break;}
   if(kind==3 && loads>=c->load_entries){r->load_full++;break;}
   if(kind==4 && stores>=c->store_entries){r->store_full++;break;}
   if(ops[renamed].dest>0 && c->physical_registers && allocated>=c->physical_registers-32){r->register_full++;break;}
   d0[renamed]=ops[renamed].src0>0?writers[ops[renamed].src0]:-1;
   d1[renamed]=ops[renamed].src1>0?writers[ops[renamed].src1]:-1;
   if(ops[renamed].dest>0){writers[ops[renamed].dest]=renamed;allocated++;}
   loads+=kind==3;stores+=kind==4;
   waiting++;renamed++;
  }
  if(cycle>=blocked_until && unresolved<0)
   for(int64_t lane=0;lane<c->fetch_width && fetched<n && fetched-renamed<c->fetch_entries;lane++)fetched++;
  if(renamed-retired>r->peak_rob)r->peak_rob=renamed-retired;
  if(waiting>r->peak_issue)r->peak_issue=waiting;
  if(fetched-renamed>r->peak_fetch)r->peak_fetch=fetched-renamed;
  if(loads>r->loads)r->loads=loads;
  if(stores>r->stores)r->stores=stores;
 }
 free(done);free(d0);free(d1);return 1;
}
