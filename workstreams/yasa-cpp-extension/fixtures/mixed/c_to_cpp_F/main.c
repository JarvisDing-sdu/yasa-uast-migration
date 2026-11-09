#include <stdlib.h>
extern int cpp_sink(const char *);
int main(void) { return cpp_sink("printf safe"); }
