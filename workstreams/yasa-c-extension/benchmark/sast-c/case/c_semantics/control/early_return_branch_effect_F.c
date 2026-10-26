/*
 * evaluation information start
 * real case = false
 * evaluation item = 控制流
 * scene introduction = 提前返回的分支内写入污点，不进入分支的路径仍是安全值
 * bind_url = c_semantics/control/early_return_branch_effect_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void early_return_branch_effect_F(int c) {
    char *p = "safe";
    if (c) { p = taint_src(); return; }
    taint_sink(p);
}
