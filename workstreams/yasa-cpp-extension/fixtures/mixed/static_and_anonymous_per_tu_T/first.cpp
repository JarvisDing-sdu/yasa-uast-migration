#include <stdlib.h>
namespace { const char *state = "printf first safe"; }
static int consume_local() { return system(state); }
extern "C" void set_first(const char *command) { state = command; }
extern "C" int consume_first() { return consume_local(); }
