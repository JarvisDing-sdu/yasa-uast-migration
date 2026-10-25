/*
 * evaluation information start
 * real case = false
 * evaluation item = 上下文敏感
 * scene introduction = 同一函数多次调用区分上下文
 * bind_url = accuracy/context_sensitive/multi_invoke_004_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static char *identity(char *x) {
    return x;
}
void multi_invoke_004_F(void) {
    char *a = identity(taint_src());
    char *b = identity("safe");
    taint_sink(b);
}
