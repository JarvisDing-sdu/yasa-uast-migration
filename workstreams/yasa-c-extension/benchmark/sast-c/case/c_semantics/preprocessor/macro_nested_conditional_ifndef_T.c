/*
 * evaluation information start
 * real case = false
 * evaluation item = 条件环境
 * scene introduction = 嵌套的未决条件组之后：#ifndef 的分支可能编译（宏可能未定义）
 * bind_url = c_semantics/preprocessor/macro_nested_conditional_ifndef_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#ifdef A
#  ifdef B
#    define USE_SAFE 1
#  else
#    define USE_SAFE 2
#  endif
#endif
#ifndef USE_SAFE
void macro_nested_conditional_ifndef_T(void) { taint_sink(taint_src()); }
#endif
