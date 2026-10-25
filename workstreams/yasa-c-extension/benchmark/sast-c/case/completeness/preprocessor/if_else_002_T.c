/*
 * evaluation information start
 * real case = true
 * evaluation item = 预处理
 * scene introduction = #if/#else 两个分支都保留
 * bind_url = completeness/preprocessor/if_else_002_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void if_else_002_T(void) {
    char *t = taint_src();
#if defined(USE_A)
    char *x = "safe";
#else
    char *x = t;
#endif
    taint_sink(x);
}
