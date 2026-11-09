#include <stdlib.h>
extern "C" int cpp_callback(const char *command) { return system(command); }
