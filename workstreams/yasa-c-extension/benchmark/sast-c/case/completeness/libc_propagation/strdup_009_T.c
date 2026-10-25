/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = strdup 返回值
 * bind_url = completeness/libc_propagation/strdup_009_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <string.h>
void strdup_009_T(void) {
    taint_sink(strdup(taint_src()));
}
