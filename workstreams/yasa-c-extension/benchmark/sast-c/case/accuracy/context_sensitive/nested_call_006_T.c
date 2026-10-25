/*
 * evaluation information start
 * real case = true
 * evaluation item = 函数调用
 * scene introduction = 多层调用
 * bind_url = accuracy/context_sensitive/nested_call_006_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void level2(char *x) { taint_sink(x); }
static void level1(char *x) { level2(x); }
void nested_call_006_T(void) {
    level1(taint_src());
}
