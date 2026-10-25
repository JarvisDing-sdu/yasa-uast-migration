/*
 * evaluation information start
 * real case = true
 * evaluation item = 预处理
 * scene introduction = switch 中 #ifdef 包裹的 case
 * bind_url = completeness/preprocessor/case_in_ifdef_005_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void case_in_ifdef_005_T(int n) {
    char *t = taint_src();
    switch (n) {
#ifdef FEATURE
    case 1:
        taint_sink(t);
        break;
#endif
    default:
        break;
    }
}
