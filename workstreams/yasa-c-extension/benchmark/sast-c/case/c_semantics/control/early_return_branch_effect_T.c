/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = 提前返回的分支内清洗，不进入分支的路径仍是污点
 * bind_url = c_semantics/control/early_return_branch_effect_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void early_return_branch_effect_T(int c) {
    char *p = taint_src();
    if (c) { p = "safe"; return; }
    taint_sink(p);
}
