/*
 * evaluation information start
 * real case = true
 * evaluation item = 赋值表达式
 * scene introduction = 连续赋值
 * bind_url = completeness/expression/assign_chain_002_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void assign_chain_002_T(void) {
    char *a, *b;
    a = b = taint_src();
    taint_sink(a);
}
