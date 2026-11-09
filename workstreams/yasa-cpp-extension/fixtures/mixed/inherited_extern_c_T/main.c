#include <stdlib.h>
extern int inherited_sink(const char *);
int main(void) { return inherited_sink(getenv("YASA_MIXED_COMMAND")); }
