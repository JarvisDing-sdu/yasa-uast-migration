/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = goto 跳转到 sink
 * bind_url = accuracy/flow_sensitive/goto_007_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void goto_007_T(int n) {
    char *t = taint_src();
    if (n) goto out;
    return;
out:
    taint_sink(t);
}
