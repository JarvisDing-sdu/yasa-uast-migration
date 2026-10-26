/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数覆盖
 * scene introduction = 清空后再追加污点
 * bind_url = c_semantics/libc/strcat_after_clean_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void strcat_after_clean_T(void) {
    char buf[64];
    strcpy(buf, "safe");
    strcat(buf, taint_src());
    taint_sink(buf);
}
