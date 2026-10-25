/*
 * evaluation information start
 * real case = true
 * evaluation item = 预处理
 * scene introduction = 宏替换为 source 调用（宏未展开，已知局限）
 * bind_url = completeness/preprocessor/macro_alias_004_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#define READ_INPUT() taint_src()
void macro_alias_004_T(void) {
    char *t = READ_INPUT();
    taint_sink(t);
}
