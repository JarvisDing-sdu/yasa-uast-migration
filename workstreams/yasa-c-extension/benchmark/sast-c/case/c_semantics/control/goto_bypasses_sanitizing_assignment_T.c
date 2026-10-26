/*
 * evaluation information start
 * real case = true
 * evaluation item = goto
 * scene introduction = goto 跳过清洗赋值
 * bind_url = c_semantics/control/goto_bypasses_sanitizing_assignment_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void goto_bypasses_sanitizing_assignment_T(void) {
    char *p = taint_src();
    goto done;
unused:
    p = "safe";
done:
    taint_sink(p);
}
