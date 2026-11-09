#include <stdlib.h>
extern void store(const char *);
extern int consume(void);
int main(void) { store(getenv("YASA_MIXED_COMMAND")); return consume(); }
