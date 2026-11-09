#include <stdlib.h>
extern void set_first(const char *);
extern int consume_first(void);
extern int consume_second(void);
int main(void) { set_first(getenv("YASA_MIXED_COMMAND")); return consume_first(); }
