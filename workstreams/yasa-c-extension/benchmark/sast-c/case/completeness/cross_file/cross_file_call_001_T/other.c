char *taint_src(void);
void taint_sink(const char *s);
void consume_other(char *x) {
    taint_sink(x);
}
