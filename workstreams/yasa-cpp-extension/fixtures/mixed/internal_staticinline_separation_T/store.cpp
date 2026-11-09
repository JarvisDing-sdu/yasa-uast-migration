#include <stdlib.h>
#include "slot.h"
extern "C" void store(const char *command) { slot(command, 1); }
extern "C" int consume_local() { return system(slot(0, 0)); }
