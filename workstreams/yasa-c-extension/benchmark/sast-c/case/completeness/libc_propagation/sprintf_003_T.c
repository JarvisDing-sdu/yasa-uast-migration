/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = sprintf 格式化污点
 * bind_url = completeness/libc_propagation/sprintf_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <stdio.h>
void sprintf_003_T(void) {
    char buf[64];
    sprintf(buf, "ls %s", taint_src());
    taint_sink(buf);
}
