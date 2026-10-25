/*
 * evaluation information start
 * real case = false
 * evaluation item = 常量
 * scene introduction = 常量字符串不是污点
 * bind_url = completeness/expression/constant_007_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void constant_007_F(void) {
    char *t = taint_src();
    taint_sink("ls -l");
}
