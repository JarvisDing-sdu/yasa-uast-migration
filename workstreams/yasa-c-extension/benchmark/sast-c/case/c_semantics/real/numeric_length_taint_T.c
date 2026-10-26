/*
 * evaluation information start
 * real case = true
 * evaluation item = 数值污点
 * scene introduction = atoi 结果作为 memcpy 长度仍是风险
 * bind_url = c_semantics/real/numeric_length_taint_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

void numeric_length_taint_T(void) {
    char a[16], b[16] = { 0 };
    memcpy(a, b, (size_t)atoi(getenv("LEN")));
}
