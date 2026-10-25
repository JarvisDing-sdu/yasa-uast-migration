/*
 * evaluation information start
 * real case = false
 * evaluation item = 真实 API
 * scene introduction = system 执行常量命令
 * bind_url = real_api/constant_system_008_F
 * evaluation information end
 */
#include <stdlib.h>
void constant_system_008_F(void) {
    char *unused = getenv("HOME");
    system("ls /tmp");
}
