#include <stdlib.h>
extern int cpp_callback(const char *);
typedef int (*callback_fn)(const char *);
static callback_fn registered;
static void c_register(callback_fn callback) { registered = callback; }
static int c_dispatch(const char *command) { return registered(command); }
int main(void) { c_register(cpp_callback); return c_dispatch("printf safe"); }
