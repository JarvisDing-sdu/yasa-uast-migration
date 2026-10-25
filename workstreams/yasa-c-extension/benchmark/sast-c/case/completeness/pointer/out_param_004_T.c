/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针别名
 * scene introduction = 输出参数把污点写回调用者
 * bind_url = completeness/pointer/out_param_004_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void produce(char **out) {
    *out = taint_src();
}
void out_param_004_T(void) {
    char *a = "safe";
    produce(&a);
    taint_sink(a);
}
