/*
 * evaluation information start
 * real case = false
 * evaluation item = 循环
 * scene introduction = while(1) 末尾无条件 break 只执行一次
 * bind_url = accuracy/flow_sensitive/loop_break_011_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void loop_break_011_F(void) {
    char *a = "safe", *b = "safe";
    while (1) {
        a = b;
        b = taint_src();
        break;
    }
    taint_sink(a);
}
