/*
 * evaluation information start
 * real case = true
 * evaluation item = 多级指针
 * scene introduction = 通过三级间接写回原变量
 * bind_url = c_semantics/pointer/triple_indirection_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void triple_indirection_T(void) {
    char *p = "safe";
    char **q = &p;
    char ***r = &q;
    char ****s = &r;
    ***s = taint_src();
    taint_sink(p);
}
