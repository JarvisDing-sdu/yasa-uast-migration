/*
 * evaluation information start
 * real case = false
 * evaluation item = 库函数传播
 * scene introduction = snprintf 只格式化常量
 * bind_url = completeness/libc_propagation/snprintf_safe_005_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <stdio.h>
void snprintf_safe_005_F(void) {
    char *t = taint_src();
    char buf[64];
    snprintf(buf, sizeof(buf), "ls %s", "/tmp");
    taint_sink(buf);
}
