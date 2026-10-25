/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针
 * scene introduction = 取地址后解引用
 * bind_url = completeness/pointer/address_of_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void address_of_001_T(void) {
    char *t = taint_src();
    char **pp = &t;
    taint_sink(*pp);
}
