/*
 * evaluation information start
 * real case = true
 * evaluation item = 头文件宏
 * scene introduction = 包含后再重定义
 * bind_url = c_semantics/preprocessor/header_macro_redefined_after_include_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#include "safe_input.h"
#undef INPUT
#define INPUT() taint_src()
void header_macro_redefined_after_include_T(void) { taint_sink(INPUT()); }
