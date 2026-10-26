/*
 * evaluation information start
 * real case = false
 * evaluation item = 常量折叠
 * scene introduction = if (1-1) 不可达
 * bind_url = c_semantics/control/dead_if_folded_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void dead_if_folded_F(void) {
    if (1 - 1) taint_sink(taint_src());
}
