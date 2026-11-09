#include <stdlib.h>
extern void store(const char *);
extern int consume_local(void);
extern int consume_other(void);
int main(void) { store(getenv("YASA_MIXED_COMMAND")); return consume_local(); }
