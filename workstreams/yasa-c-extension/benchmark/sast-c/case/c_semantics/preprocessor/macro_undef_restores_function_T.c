/*
 * evaluation information start
 * real case = true
 * evaluation item = 宏时序
 * scene introduction = #undef 后恢复为真实函数调用
 * bind_url = c_semantics/preprocessor/macro_undef_restores_function_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#define taint_src() "safe"
#undef taint_src
void macro_undef_restores_function_T(void) { taint_sink(taint_src()); }
