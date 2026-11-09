#include <stdlib.h>
extern "C" const char *c_source(void);
int main() { const char *command = c_source(); return system(command); }
