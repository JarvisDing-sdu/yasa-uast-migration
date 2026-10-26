/*
 * evaluation information start
 * real case = false
 * evaluation item = 格式串取参
 * scene introduction = 只使用第一个参数
 * bind_url = c_semantics/libc/snprintf_second_argument_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void snprintf_second_argument_F(void) {
    char buf[64];
    snprintf(buf, sizeof buf, "%s", "safe", taint_src());
    taint_sink(buf);
}
