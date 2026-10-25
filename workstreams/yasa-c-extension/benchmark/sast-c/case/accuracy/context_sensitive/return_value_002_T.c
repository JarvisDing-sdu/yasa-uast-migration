/*
 * evaluation information start
 * real case = true
 * evaluation item = 函数调用
 * scene introduction = 污点经返回值传出
 * bind_url = accuracy/context_sensitive/return_value_002_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static char *identity(char *x) {
    return x;
}
void return_value_002_T(void) {
    taint_sink(identity(taint_src()));
}
