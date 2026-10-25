/*
 * evaluation information start
 * real case = true
 * evaluation item = 类型转换
 * scene introduction = 多重指针类型转换
 * bind_url = completeness/expression/cast_004_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void cast_004_T(void) {
    char *t = taint_src();
    taint_sink((const char *)(void *)t);
}
