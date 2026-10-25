/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = while 循环
 * bind_url = accuracy/flow_sensitive/while_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void while_003_T(int n) {
    char *t = taint_src();
    while (n-- > 0) {
        taint_sink(t);
    }
}
