/*
 * evaluation information start
 * real case = true
 * evaluation item = 函数调用
 * scene introduction = 先声明后定义的函数
 * bind_url = accuracy/context_sensitive/forward_decl_009_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void later(char *x);
void forward_decl_009_T(void) {
    later(taint_src());
}
static void later(char *x) { taint_sink(x); }
