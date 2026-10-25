/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = if 分支内的 sink
 * bind_url = accuracy/flow_sensitive/if_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void if_001_T(int n) {
    char *t = taint_src();
    if (n > 0) {
        taint_sink(t);
    }
}
