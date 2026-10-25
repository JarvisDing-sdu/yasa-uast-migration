/*
 * evaluation information start
 * real case = true
 * evaluation item = 条件表达式
 * scene introduction = 三目运算符任一分支被污染
 * bind_url = completeness/expression/conditional_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void conditional_003_T(int n) {
    char *t = taint_src();
    char *a = n ? t : "safe";
    taint_sink(a);
}
