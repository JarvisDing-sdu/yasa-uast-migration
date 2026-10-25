/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = for 循环
 * bind_url = accuracy/flow_sensitive/for_004_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void for_004_T(void) {
    char *t = taint_src();
    for (int i = 0; i < 3; i++) {
        taint_sink(t);
    }
}
