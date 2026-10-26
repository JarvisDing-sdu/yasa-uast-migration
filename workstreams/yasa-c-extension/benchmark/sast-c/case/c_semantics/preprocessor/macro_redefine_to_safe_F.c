/*
 * evaluation information start
 * real case = false
 * evaluation item = 宏时序
 * scene introduction = #undef 后重定义为常量
 * bind_url = c_semantics/preprocessor/macro_redefine_to_safe_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#define INPUT() taint_src()
#undef INPUT
#define INPUT() "safe"
void macro_redefine_to_safe_F(void) { taint_sink(INPUT()); }
