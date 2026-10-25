/*
 * evaluation information start
 * real case = true
 * evaluation item = 函数调用
 * scene introduction = 递归函数
 * bind_url = accuracy/context_sensitive/recursion_010_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void recurse(char *x, int n) {
    if (n <= 0) {
        taint_sink(x);
        return;
    }
    recurse(x, n - 1);
}
void recursion_010_T(void) {
    recurse(taint_src(), 3);
}
