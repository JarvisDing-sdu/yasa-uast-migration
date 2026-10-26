/*
 * evaluation information start
 * real case = true
 * evaluation item = goto
 * scene introduction = goto 跳出内层块到外层标签
 * bind_url = c_semantics/control/goto_out_of_block_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void goto_out_of_block_T(void) {
    char *p = taint_src();
    { goto out; }
    p = "safe";
out:
    taint_sink(p);
}
