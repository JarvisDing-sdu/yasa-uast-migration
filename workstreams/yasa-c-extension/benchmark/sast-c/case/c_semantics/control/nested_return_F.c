/*
 * evaluation information start
 * real case = false
 * evaluation item = return 传播
 * scene introduction = 内层块 return 后外层后续语句不可达
 * bind_url = c_semantics/control/nested_return_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void nested_return_F(void) {
    { return; }
    taint_sink(taint_src());
}
