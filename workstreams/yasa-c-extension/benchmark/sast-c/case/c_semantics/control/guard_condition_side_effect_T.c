/*
 * evaluation information start
 * real case = true
 * evaluation item = 控制流
 * scene introduction = 提前返回的 if 条件本身写入了污点（如 if (sscanf(...) != 1) return;），条件的副作用保留
 * bind_url = c_semantics/control/guard_condition_side_effect_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void guard_condition_side_effect_T(void) {
    char *p = "safe";
    if ((p = taint_src()) == 0) { return; }
    taint_sink(p);
}
