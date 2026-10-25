/*
 * evaluation information start
 * real case = false
 * evaluation item = 路径敏感
 * scene introduction = return 之后的 sink
 * bind_url = accuracy/flow_sensitive/after_return_010_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void after_return_010_F(void) {
    char *t = taint_src();
    return;
    taint_sink(t);
}
