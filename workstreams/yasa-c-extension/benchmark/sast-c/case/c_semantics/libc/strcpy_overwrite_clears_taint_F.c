/*
 * evaluation information start
 * real case = false
 * evaluation item = 库函数覆盖
 * scene introduction = strcpy 用常量完整覆盖
 * bind_url = c_semantics/libc/strcpy_overwrite_clears_taint_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void strcpy_overwrite_clears_taint_F(void) {
    char buf[64];
    snprintf(buf, sizeof buf, "%s", taint_src());
    strcpy(buf, "safe");
    taint_sink(buf);
}
