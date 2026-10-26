/*
 * evaluation information start
 * real case = true
 * evaluation item = return 传播
 * scene introduction = 条件 return 之后的语句仍可达
 * bind_url = c_semantics/control/conditional_return_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void conditional_return_T(int c) {
    if (c) { return; }
    taint_sink(taint_src());
}
