/*
 * evaluation information start
 * real case = false
 * evaluation item = 宏替换
 * scene introduction = GNU , ## __VA_ARGS__：变参为空时去掉逗号
 * bind_url = c_semantics/preprocessor/macro_gnu_comma_paste_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
#define SINK(s, ...) taint_sink(s, ##__VA_ARGS__)
void macro_gnu_comma_paste_T(void) { SINK(taint_src()); }
