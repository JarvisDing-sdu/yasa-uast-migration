/*
 * evaluation information start
 * real case = true
 * evaluation item = 库函数传播
 * scene introduction = sscanf 从污点字符串解析
 * bind_url = completeness/libc_propagation/sscanf_008_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
#include <stdio.h>
void sscanf_008_T(void) {
    char word[32];
    sscanf(taint_src(), "%31s", word);
    taint_sink(word);
}
