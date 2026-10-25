/*
 * evaluation information start
 * real case = true
 * evaluation item = 真实 API
 * scene introduction = fgets → printf 格式化字符串
 * bind_url = real_api/fgets_printf_002_T
 * evaluation information end
 */
#include <stdio.h>
void fgets_printf_002_T(void) {
    char buf[128];
    fgets(buf, sizeof(buf), stdin);
    printf(buf);
}
