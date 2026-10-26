/*
 * evaluation information start
 * real case = true
 * evaluation item = 数值污点
 * scene introduction = atoi 结果写入格式串（选择位置参数），格式串 sink 仍危险
 * bind_url = c_semantics/real/numeric_format_index_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

void numeric_format_index_T(void) {
    char fmt[64];
    snprintf(fmt, sizeof fmt, "%%%d$s\n", atoi(getenv("INDEX")));
    printf(fmt, "a", "b");
}
