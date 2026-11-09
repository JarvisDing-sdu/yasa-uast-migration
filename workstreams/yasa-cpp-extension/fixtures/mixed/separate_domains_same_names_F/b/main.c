#include <stdlib.h>
extern int domain_sink(const char *);
int main(void) { return domain_sink("printf safe"); }
