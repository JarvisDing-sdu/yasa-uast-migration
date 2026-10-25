/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针别名
 * scene introduction = 通过指针写入后读原变量
 * bind_url = completeness/pointer/write_through_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void write_through_003_T(void) {
    char *a = "safe";
    char **pp = &a;
    *pp = taint_src();
    taint_sink(a);
}
