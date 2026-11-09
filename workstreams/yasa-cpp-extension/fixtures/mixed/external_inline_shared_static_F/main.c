#include <stdlib.h>
extern void store(const char *);
extern int consume(void);
int main(void) { store("printf safe"); return consume(); }
