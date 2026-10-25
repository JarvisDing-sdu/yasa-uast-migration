/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = if/else 两分支汇合
 * bind_url = accuracy/flow_sensitive/if_else_002_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void if_else_002_T(int n) {
    char *a;
    if (n) a = taint_src(); else a = "safe";
    taint_sink(a);
}
