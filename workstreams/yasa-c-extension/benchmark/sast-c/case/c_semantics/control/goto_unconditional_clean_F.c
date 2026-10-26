/*
 * evaluation information start
 * real case = false
 * evaluation item = goto
 * scene introduction = 无条件 goto 到清洗标签
 * bind_url = c_semantics/control/goto_unconditional_clean_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void goto_unconditional_clean_F(void) {
    char *p = taint_src();
    goto clean;
skipped:
    p = taint_src();
clean:
    p = "safe";
    taint_sink(p);
}
