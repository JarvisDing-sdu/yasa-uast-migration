/*
 * evaluation information start
 * real case = false
 * evaluation item = 指针读取
 * scene introduction = 指针读取被指变量当前值（已被覆盖为安全）
 * bind_url = c_semantics/pointer/deref_reads_current_value_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void deref_reads_current_value_F(void) {
    char *p = taint_src();
    char **q = &p;
    p = "safe";
    taint_sink(*q);
}
