/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = strcat 追加污点
 * bind_url = completeness/libc_propagation/strcat_002_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <string.h>
void strcat_002_T(void) {
    char buf[64] = "cmd ";
    strcat(buf, taint_src());
    taint_sink(buf);
}
