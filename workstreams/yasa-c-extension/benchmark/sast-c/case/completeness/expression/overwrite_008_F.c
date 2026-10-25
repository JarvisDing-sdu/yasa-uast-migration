/*
 * evaluation information start
 * real case = false
 * evaluation item = 流敏感
 * scene introduction = 污点被常量覆盖后再使用
 * bind_url = completeness/expression/overwrite_008_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void overwrite_008_F(void) {
    char *a = taint_src();
    a = "safe";
    taint_sink(a);
}
