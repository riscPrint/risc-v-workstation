#include <stdint.h>
#include "util.h"
/* One node per 64 bytes. Each load supplies the next address. */
static struct node { struct node *next; uintptr_t pad[64/sizeof(uintptr_t)-1]; } nodes[4096];
int main(void) {
  for (unsigned i=0; i<4096; ++i) nodes[i].next = &nodes[(i+17)%4096];
  volatile struct node *p = nodes;
  setStats(1);
  for (unsigned i=0; i<16384; ++i) p = p->next;
  setStats(0);
  return p != nodes;
}
