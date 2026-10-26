/*
 * evaluation information start
 * real case = true
 * evaluation item = 指针读取
 * scene introduction = 指针读取被指变量当前值（后被污染）
 * bind_url = c_semantics/pointer/deref_reads_current_value_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void deref_reads_current_value_T(void) {
    char *p = "safe";
    char **q = &p;
    p = taint_src();
    taint_sink(*q);
}
