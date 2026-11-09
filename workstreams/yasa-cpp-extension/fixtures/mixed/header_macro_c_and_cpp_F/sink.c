#define HEADER_UNTRUSTED 1
#include "shared.h"
int c_sink(const char *command) { return system(command); }
int c_probe(void) { return c_sink(header_command()); }
