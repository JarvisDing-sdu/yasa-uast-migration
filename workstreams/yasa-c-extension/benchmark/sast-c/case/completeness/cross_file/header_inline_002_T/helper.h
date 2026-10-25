#ifndef HELPER_H
#define HELPER_H
char *taint_src(void);
void taint_sink(const char *s);
static inline void helper_sink(char *x) {
    taint_sink(x);
}
#endif
