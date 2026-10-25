/*
 * evaluation information start
 * real case = false
 * evaluation item = 路径敏感
 * scene introduction = 永假条件中的 sink
 * bind_url = accuracy/flow_sensitive/dead_branch_009_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void dead_branch_009_F(void) {
    char *t = taint_src();
    if (0) {
        taint_sink(t);
    }
}
