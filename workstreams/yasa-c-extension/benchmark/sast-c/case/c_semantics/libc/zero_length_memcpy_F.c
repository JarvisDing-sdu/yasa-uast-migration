/*
 * evaluation information start
 * real case = false
 * evaluation item = 库函数长度
 * scene introduction = 长度为 0 的 memcpy 不写入
 * bind_url = c_semantics/libc/zero_length_memcpy_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void zero_length_memcpy_F(void) {
    char buf[64] = "safe";
    memcpy(buf, taint_src(), 0);
    taint_sink(buf);
}
