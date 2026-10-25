/*
 * evaluation information start
 * real case = true
 * evaluation item = 逗号表达式
 * scene introduction = 逗号表达式取最后一个值
 * bind_url = completeness/expression/comma_005_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void comma_005_T(void) {
    char *a = 0;
    a = (a, taint_src());
    taint_sink(a);
}
