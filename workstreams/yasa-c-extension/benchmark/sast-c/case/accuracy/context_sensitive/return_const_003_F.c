/*
 * evaluation information start
 * real case = false
 * evaluation item = 函数调用
 * scene introduction = 函数返回常量
 * bind_url = accuracy/context_sensitive/return_const_003_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static char *constant(char *x) {
    return "safe";
}
void return_const_003_F(void) {
    taint_sink(constant(taint_src()));
}
