#include <stdlib.h>
extern "C" int domain_sink(const char *command) { return system(command); }
