/*
 * evaluation information start
 * real case = true
 * evaluation item = 预处理
 * scene introduction = #ifdef 包裹的函数
 * bind_url = completeness/preprocessor/ifdef_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#ifdef ENABLE_FEATURE
void ifdef_001_T(void) {
    taint_sink(taint_src());
}
#endif
