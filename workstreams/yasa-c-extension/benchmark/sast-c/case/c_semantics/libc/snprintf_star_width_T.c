/*
 * evaluation information start
 * real case = true
 * evaluation item = 格式串取参
 * scene introduction = %*s 先消耗宽度再消耗字符串
 * bind_url = c_semantics/libc/snprintf_star_width_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void snprintf_star_width_T(void) {
    char buf[64];
    snprintf(buf, sizeof buf, "%*s", 4, taint_src());
    taint_sink(buf);
}
