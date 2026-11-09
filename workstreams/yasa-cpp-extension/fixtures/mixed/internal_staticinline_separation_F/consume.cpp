#include <stdlib.h>
#include "slot.h"
extern "C" int consume_other() { return system(slot(0, 0)); }
