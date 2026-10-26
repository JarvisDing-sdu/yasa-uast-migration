/*
 * evaluation information start
 * real case = true
 * evaluation item = 宏时序
 * scene introduction = 使用之后才定义的宏不影响之前的代码
 * bind_url = c_semantics/preprocessor/macro_defined_after_use_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void macro_defined_after_use_T(void) { char *p = taint_src(); taint_sink(p); }
#define taint_src() "safe"
