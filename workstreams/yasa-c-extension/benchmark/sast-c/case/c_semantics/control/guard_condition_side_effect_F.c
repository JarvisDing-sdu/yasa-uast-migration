/*
 * evaluation information start
 * real case = false
 * evaluation item = 控制流
 * scene introduction = if 条件写入安全值，返回分支内的写入不流到 if 之后
 * bind_url = c_semantics/control/guard_condition_side_effect_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void guard_condition_side_effect_F(void) {
    char *p = taint_src();
    if ((p = "safe") == 0) { p = taint_src(); return; }
    taint_sink(p);
}
