/*
 * evaluation information start
 * real case = false
 * evaluation item = 条件定义
 * scene introduction = 默认目标下 Windows 分支的同名函数不参与
 * bind_url = c_semantics/preprocessor/conditional_duplicate_platform_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#ifdef _WIN32
char *pick_platform(void) { return taint_src(); }
#else
char *pick_platform(void) { return "safe"; }
#endif
void conditional_duplicate_platform_F(void) { taint_sink(pick_platform()); }
