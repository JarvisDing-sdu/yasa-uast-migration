/*
 * evaluation information start
 * real case = false
 * evaluation item = 格式串取参
 * scene introduction = %% 不消耗参数
 * bind_url = c_semantics/libc/snprintf_percent_literal_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void snprintf_percent_literal_F(void) {
    char buf[64];
    snprintf(buf, sizeof buf, "100%%", taint_src());
    taint_sink(buf);
}
