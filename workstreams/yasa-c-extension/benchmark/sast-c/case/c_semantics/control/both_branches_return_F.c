/*
 * evaluation information start
 * real case = false
 * evaluation item = return 传播
 * scene introduction = 两个分支都 return 后语句不可达
 * bind_url = c_semantics/control/both_branches_return_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void both_branches_return_F(int c) {
    if (c) { return; } else { return; }
    taint_sink(taint_src());
}
