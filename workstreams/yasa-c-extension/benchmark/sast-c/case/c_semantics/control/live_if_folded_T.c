/*
 * evaluation information start
 * real case = true
 * evaluation item = 常量折叠
 * scene introduction = if (2-1) 可达
 * bind_url = c_semantics/control/live_if_folded_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void live_if_folded_T(void) {
    if (2 - 1) taint_sink(taint_src());
}
