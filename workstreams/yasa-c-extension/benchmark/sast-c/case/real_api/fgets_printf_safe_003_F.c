/*
 * evaluation information start
 * real case = false
 * evaluation item = 真实 API
 * scene introduction = fgets 读入后用 %s 打印
 * bind_url = real_api/fgets_printf_safe_003_F
 * evaluation information end
 */
#include <stdio.h>
void fgets_printf_safe_003_F(void) {
    char buf[128];
    fgets(buf, sizeof(buf), stdin);
    printf("%s", buf);
}
