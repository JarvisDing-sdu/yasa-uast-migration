/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = 循环携带依赖
 * bind_url = accuracy/flow_sensitive/loop_carried_008_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void loop_carried_008_T(void) {
    char *a = "safe", *b = "safe";
    for (int i = 0; i < 2; i++) {
        a = b;
        b = taint_src();
    }
    taint_sink(a);
}
