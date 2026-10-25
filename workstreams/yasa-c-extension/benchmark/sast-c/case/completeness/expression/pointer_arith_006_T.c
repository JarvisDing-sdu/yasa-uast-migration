/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针运算
 * scene introduction = 指针偏移仍指向污点数据
 * bind_url = completeness/expression/pointer_arith_006_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void pointer_arith_006_T(void) {
    char *t = taint_src();
    taint_sink(t + 2);
}
