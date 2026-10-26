/*
 * evaluation information start
 * real case = true
 * evaluation item = 条件定义
 * scene introduction = #if/#else 同名函数，两个配置都分析
 * bind_url = c_semantics/preprocessor/conditional_duplicate_function_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#ifdef FEATURE
char *pick(void) { return "safe"; }
#else
char *pick(void) { return taint_src(); }
#endif
void conditional_duplicate_function_T(void) { taint_sink(pick()); }
