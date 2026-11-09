#include <stdlib.h>
extern "C" int c_sink(const char *);
int same_name(const char *command) { (void)command; return 0; }
int main() { return same_name(getenv("YASA_MIXED_COMMAND")); }
