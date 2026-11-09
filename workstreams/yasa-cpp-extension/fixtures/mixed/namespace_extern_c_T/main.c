#include <stdlib.h>
extern int namespace_sink(const char *);
int main(void) { return namespace_sink(getenv("YASA_MIXED_COMMAND")); }
