/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = 被调函数向调用者缓冲区 strcpy
 * bind_url = completeness/libc_propagation/out_buffer_param_011_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <string.h>
static void fill(char *dst) {
    strcpy(dst, taint_src());
}
void out_buffer_param_011_T(void) {
    char buf[64];
    fill(buf);
    taint_sink(buf);
}
