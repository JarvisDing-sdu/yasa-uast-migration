/*
 * evaluation information start
 * real case = true
 * evaluation item = 函数指针
 * scene introduction = 通过函数指针调用
 * bind_url = accuracy/context_sensitive/function_pointer_007_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void consume(char *x) { taint_sink(x); }
void function_pointer_007_T(void) {
    void (*fp)(char *) = consume;
    fp(taint_src());
}
