/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = strncpy 拷贝污点
 * bind_url = completeness/libc_propagation/strncpy_007_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <string.h>
void strncpy_007_T(void) {
    char buf[64];
    strncpy(buf, taint_src(), sizeof(buf) - 1);
    taint_sink(buf);
}
