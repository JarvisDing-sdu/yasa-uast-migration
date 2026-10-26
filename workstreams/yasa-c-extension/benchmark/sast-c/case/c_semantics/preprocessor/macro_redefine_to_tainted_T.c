/*
 * evaluation information start
 * real case = true
 * evaluation item = 宏时序
 * scene introduction = #undef 后重定义为污点
 * bind_url = c_semantics/preprocessor/macro_redefine_to_tainted_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#define INPUT() "safe"
#undef INPUT
#define INPUT() taint_src()
void macro_redefine_to_tainted_T(void) { taint_sink(INPUT()); }
