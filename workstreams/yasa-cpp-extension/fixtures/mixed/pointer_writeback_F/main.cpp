#include <stdlib.h>
extern "C" void c_fill(const char **);
int main() { const char *command = "printf initial"; c_fill(&command); return system(command); }
