/*
 * evaluation information start
 * real case = true
 * evaluation item = 全局变量
 * scene introduction = 全局变量跨函数传递
 * bind_url = accuracy/context_sensitive/global_var_011_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static char *g_value;
static void store(void) { g_value = taint_src(); }
void global_var_011_T(void) {
    store();
    taint_sink(g_value);
}
