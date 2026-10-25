/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针别名
 * scene introduction = 两个指针指向同一变量，一写一读
 * bind_url = completeness/pointer/two_pointers_006_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void two_pointers_006_T(void) {
    char *data = "safe";
    char **writer = &data;
    char **reader = &data;
    *writer = taint_src();
    taint_sink(*reader);
}
