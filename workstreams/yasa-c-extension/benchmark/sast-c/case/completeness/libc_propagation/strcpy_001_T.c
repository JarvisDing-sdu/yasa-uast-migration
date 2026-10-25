/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = strcpy 把污点写入目标缓冲区
 * bind_url = completeness/libc_propagation/strcpy_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <string.h>
void strcpy_001_T(void) {
    char buf[64];
    strcpy(buf, taint_src());
    taint_sink(buf);
}
