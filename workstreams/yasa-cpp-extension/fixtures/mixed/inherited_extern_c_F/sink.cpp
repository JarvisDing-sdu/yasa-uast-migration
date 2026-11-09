#include <stdlib.h>
extern "C" int inherited_sink(const char *);
int inherited_sink(const char *command) { return system(command); }
