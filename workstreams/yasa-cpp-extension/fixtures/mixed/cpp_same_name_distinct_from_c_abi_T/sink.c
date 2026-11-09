#include <stdlib.h>
int same_name(const char *command) { (void)command; return 0; }
int c_sink(const char *command) { return system(command); }
