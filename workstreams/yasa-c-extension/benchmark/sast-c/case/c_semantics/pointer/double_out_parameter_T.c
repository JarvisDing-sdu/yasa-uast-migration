/*
 * evaluation information start
 * real case = true
 * evaluation item = 多级输出参数
 * scene introduction = 通过 char *** 参数写回调用方
 * bind_url = c_semantics/pointer/double_out_parameter_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
static void set2(char ***r) { **r = taint_src(); }
void double_out_parameter_T(void) {
    char *p = "safe";
    char **q = &p;
    set2(&q);
    taint_sink(p);
}
