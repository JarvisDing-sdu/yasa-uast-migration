/*
 * evaluation information start
 * real case = false
 * evaluation item = 指针别名
 * scene introduction = 输出参数写入常量
 * bind_url = completeness/pointer/out_param_005_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
static void produce_safe(char **out) {
    *out = "safe";
}
void out_param_005_F(void) {
    char *a = 0;
    produce_safe(&a);
    taint_sink(a);
}
