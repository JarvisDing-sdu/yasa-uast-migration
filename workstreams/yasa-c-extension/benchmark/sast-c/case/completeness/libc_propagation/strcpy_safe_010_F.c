/*
 * evaluation information start
 * real case = false
 * evaluation item = 库函数传播
 * scene introduction = strcpy 拷贝常量
 * bind_url = completeness/libc_propagation/strcpy_safe_010_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <string.h>
void strcpy_safe_010_F(void) {
    char *t = taint_src();
    char buf[64];
    strcpy(buf, "safe");
    taint_sink(buf);
}
