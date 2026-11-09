#include <stdlib.h>
extern "C" int c_sink(const char *);
int main() { return c_sink("printf safe"); }
