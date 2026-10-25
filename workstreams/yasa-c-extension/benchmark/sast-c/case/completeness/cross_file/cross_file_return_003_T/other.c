char *taint_src(void);
void taint_sink(const char *s);
char *fetch_other(void) {
    return taint_src();
}
