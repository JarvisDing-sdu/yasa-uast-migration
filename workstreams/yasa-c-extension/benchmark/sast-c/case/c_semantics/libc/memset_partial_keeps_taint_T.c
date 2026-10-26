/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数覆盖
 * scene introduction = memset 部分覆盖保留其余内容
 * bind_url = c_semantics/libc/memset_partial_keeps_taint_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void memset_partial_keeps_taint_T(void) {
    char buf[64];
    snprintf(buf, sizeof buf, "%s", taint_src());
    memset(buf, '-', 2);
    taint_sink(buf);
}
