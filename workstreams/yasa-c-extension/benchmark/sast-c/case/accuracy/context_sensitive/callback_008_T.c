/*
 * evaluation information start
 * real case = true
 * evaluation item = 函数指针
 * scene introduction = 回调函数参数
 * bind_url = accuracy/context_sensitive/callback_008_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void consume(char *x) { taint_sink(x); }
static void apply(void (*cb)(char *), char *arg) { cb(arg); }
void callback_008_T(void) {
    apply(consume, taint_src());
}
