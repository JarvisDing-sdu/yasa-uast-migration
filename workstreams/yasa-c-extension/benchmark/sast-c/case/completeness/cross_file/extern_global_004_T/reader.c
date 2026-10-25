char *taint_src(void);
void taint_sink(const char *s);
extern char *shared_value;
void read_shared(void) {
    taint_sink(shared_value);
}
