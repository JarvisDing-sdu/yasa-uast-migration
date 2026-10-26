/*
 * evaluation information start
 * real case = false
 * evaluation item = 库函数覆盖
 * scene introduction = memset 完整覆盖
 * bind_url = c_semantics/libc/memset_overwrite_clears_taint_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void memset_overwrite_clears_taint_F(void) {
    char buf[64];
    snprintf(buf, sizeof buf, "%s", taint_src());
    memset(buf, 0, sizeof buf);
    taint_sink(buf);
}
