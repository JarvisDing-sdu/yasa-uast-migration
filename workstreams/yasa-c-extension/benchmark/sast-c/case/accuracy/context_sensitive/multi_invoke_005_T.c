/*
 * evaluation information start
 * real case = true
 * evaluation item = 上下文敏感
 * scene introduction = 同一函数多次调用取被污染上下文
 * bind_url = accuracy/context_sensitive/multi_invoke_005_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static char *identity(char *x) {
    return x;
}
void multi_invoke_005_T(void) {
    char *a = identity("safe");
    char *b = identity(taint_src());
    taint_sink(b);
}
