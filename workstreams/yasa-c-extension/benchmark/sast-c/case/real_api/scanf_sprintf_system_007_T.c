/*
 * evaluation information start
 * real case = true
 * evaluation item = 真实 API
 * scene introduction = scanf → sprintf 拼接 → system
 * bind_url = real_api/scanf_sprintf_system_007_T
 * evaluation information end
 */
#include <stdio.h>
#include <stdlib.h>
void scanf_sprintf_system_007_T(void) {
    char name[64];
    char cmd[128];
    scanf("%63s", name);
    sprintf(cmd, "grep %s /etc/passwd", name);
    system(cmd);
}
