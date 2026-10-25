/*
 * evaluation information start
 * real case = true
 * evaluation item = 预处理
 * scene introduction = 头文件保护宏内的定义
 * bind_url = completeness/preprocessor/header_guard_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#ifndef HEADER_GUARD_003
#define HEADER_GUARD_003
void header_guard_003_T(void) {
    taint_sink(taint_src());
}
#endif
