#include <stdlib.h>
namespace { const char *state = "printf second safe"; }
static int consume_local() { return system(state); }
extern "C" int consume_second() { return consume_local(); }
