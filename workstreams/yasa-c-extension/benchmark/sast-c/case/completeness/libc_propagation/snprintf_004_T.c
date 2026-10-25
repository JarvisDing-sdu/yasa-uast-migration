/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = snprintf 格式化污点
 * bind_url = completeness/libc_propagation/snprintf_004_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <stdio.h>
void snprintf_004_T(void) {
    char buf[64];
    snprintf(buf, sizeof(buf), "ls %s", taint_src());
    taint_sink(buf);
}
