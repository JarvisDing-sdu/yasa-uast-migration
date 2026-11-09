#include <stdlib.h>
#include "slot.h"
extern "C" int consume() { return system(slot(0, 0)); }
