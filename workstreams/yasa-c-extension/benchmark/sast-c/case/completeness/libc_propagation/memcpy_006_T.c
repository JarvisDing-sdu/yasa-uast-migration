/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = memcpy 拷贝污点
 * bind_url = completeness/libc_propagation/memcpy_006_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <string.h>
void memcpy_006_T(void) {
    char buf[64];
    char *t = taint_src();
    memcpy(buf, t, 16);
    taint_sink(buf);
}
