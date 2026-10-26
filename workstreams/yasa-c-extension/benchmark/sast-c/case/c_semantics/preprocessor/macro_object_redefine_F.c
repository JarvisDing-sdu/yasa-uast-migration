/*
 * evaluation information start
 * real case = false
 * evaluation item = 宏时序
 * scene introduction = 对象宏重定义为常量
 * bind_url = c_semantics/preprocessor/macro_object_redefine_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#define CMD taint_src()
#undef CMD
#define CMD "safe"
void macro_object_redefine_F(void) { taint_sink(CMD); }
