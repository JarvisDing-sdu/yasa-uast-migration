/*
 * evaluation information start
 * real case = true
 * evaluation item = 头文件宏
 * scene introduction = 头文件中定义的宏
 * bind_url = c_semantics/preprocessor/header_macro_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#include "input.h"
void header_macro_T(void) { taint_sink(INPUT()); }
