/*
 * evaluation information start
 * real case = false
 * evaluation item = 条件环境
 * scene introduction = 外层 #else 路径上宏从未定义：不使用嵌套组里的定义
 * bind_url = c_semantics/preprocessor/macro_nested_conditional_else_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#ifdef A
#  ifdef B
#    define INPUT() taint_src()
#  else
#    define INPUT() taint_src()
#  endif
#else
char *INPUT(void) { return "safe"; }
void macro_nested_conditional_else_F(void) { taint_sink(INPUT()); }
#endif
