/*
 * evaluation information start
 * real case = true
 * evaluation item = 赋值表达式
 * scene introduction = 直接赋值
 * bind_url = completeness/expression/assign_direct_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void assign_direct_001_T(void) {
    char *a = taint_src();
    taint_sink(a);
}
