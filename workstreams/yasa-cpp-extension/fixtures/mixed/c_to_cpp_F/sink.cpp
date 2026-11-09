#include <stdlib.h>
extern "C" int cpp_sink(const char *command) { return system(command); }
