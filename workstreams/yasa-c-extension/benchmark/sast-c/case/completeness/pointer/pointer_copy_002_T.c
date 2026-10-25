/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针
 * scene introduction = 指针复制
 * bind_url = completeness/pointer/pointer_copy_002_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void pointer_copy_002_T(void) {
    char *a = taint_src();
    char *b = a;
    taint_sink(b);
}
