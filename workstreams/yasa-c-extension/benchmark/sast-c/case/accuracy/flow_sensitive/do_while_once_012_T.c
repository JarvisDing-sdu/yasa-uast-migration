/*
 * evaluation information start
 * real case = true
 * evaluation item = 循环
 * scene introduction = do { } while (0) 循环体执行一次
 * bind_url = accuracy/flow_sensitive/do_while_once_012_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void do_while_once_012_T(void) {
    char *a = "safe";
    do {
        a = taint_src();
    } while (0);
    taint_sink(a);
}
