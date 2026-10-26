/*
 * evaluation information start
 * real case = false
 * evaluation item = 数值污点
 * scene introduction = atoi 结果格式化为数字后执行命令
 * bind_url = c_semantics/real/numeric_command_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

void numeric_command_F(void) {
    char cmd[64];
    snprintf(cmd, sizeof cmd, "ls -l | head -n %d", atoi(getenv("COUNT")));
    system(cmd);
}
