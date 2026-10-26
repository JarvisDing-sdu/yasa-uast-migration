/*
 * evaluation information start
 * real case = false
 * evaluation item = 头文件宏
 * scene introduction = 头文件宏展开为常量
 * bind_url = c_semantics/preprocessor/header_macro_safe_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#include "safe_input.h"
void header_macro_safe_F(void) { taint_sink(INPUT()); }
