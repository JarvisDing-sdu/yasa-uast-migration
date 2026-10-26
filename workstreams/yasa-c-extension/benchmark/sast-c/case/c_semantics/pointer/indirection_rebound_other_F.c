/*
 * evaluation information start
 * real case = false
 * evaluation item = 指针重绑定
 * scene introduction = *r 重新指向另一变量后写入不影响原变量
 * bind_url = c_semantics/pointer/indirection_rebound_other_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void indirection_rebound_other_F(void) {
    char *p = "safe", *o = "safe";
    char **q = &p;
    char ***r = &q;
    *r = &o;
    **r = taint_src();
    taint_sink(p);
}
