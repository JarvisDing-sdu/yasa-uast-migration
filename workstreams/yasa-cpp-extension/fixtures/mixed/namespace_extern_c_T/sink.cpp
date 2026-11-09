#include <stdlib.h>
namespace bridge {
extern "C" int namespace_sink(const char *command) { return system(command); }
}
