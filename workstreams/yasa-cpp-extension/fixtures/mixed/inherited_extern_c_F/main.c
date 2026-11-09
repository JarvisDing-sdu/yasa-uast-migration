#include <stdlib.h>
extern int inherited_sink(const char *);
int main(void) { return inherited_sink("printf safe"); }
