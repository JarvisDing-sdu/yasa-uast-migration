/*
 * evaluation information start
 * real case = true
 * evaluation item = 函数调用
 * scene introduction = 污点作为参数传入
 * bind_url = accuracy/context_sensitive/param_pass_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void consume(char *x) {
    taint_sink(x);
}
void param_pass_001_T(void) {
    consume(taint_src());
}
