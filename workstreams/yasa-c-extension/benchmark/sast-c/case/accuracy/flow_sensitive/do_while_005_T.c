/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = do-while 循环
 * bind_url = accuracy/flow_sensitive/do_while_005_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void do_while_005_T(int n) {
    char *t = taint_src();
    do {
        taint_sink(t);
    } while (--n > 0);
}
