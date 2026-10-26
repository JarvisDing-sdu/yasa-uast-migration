/*
 * evaluation information start
 * real case = false
 * evaluation item = continue 传播
 * scene introduction = continue 之后循环体其余部分不执行
 * bind_url = c_semantics/control/continue_skips_rest_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void continue_skips_rest_F(void) {
    char *p = "safe";
    for (int i = 0; i < 2; i++) { continue; p = taint_src(); }
    taint_sink(p);
}
