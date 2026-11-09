#define HEADER_UNTRUSTED 1
#include "shared.h"
extern "C" int c_sink(const char *);
extern "C" int c_probe(void);
int main() { c_probe(); return c_sink(header_command()); }
