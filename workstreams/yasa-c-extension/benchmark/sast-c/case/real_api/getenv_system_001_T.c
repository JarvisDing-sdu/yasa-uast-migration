/*
 * evaluation information start
 * real case = true
 * evaluation item = 真实 API
 * scene introduction = getenv → system
 * bind_url = real_api/getenv_system_001_T
 * evaluation information end
 */
#include <stdlib.h>
void getenv_system_001_T(void) {
    char *cmd = getenv("CMD");
    system(cmd);
}
