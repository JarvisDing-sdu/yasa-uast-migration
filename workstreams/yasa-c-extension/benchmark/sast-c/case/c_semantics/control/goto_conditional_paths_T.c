/*
 * evaluation information start
 * real case = true
 * evaluation item = goto
 * scene introduction = 条件 goto：一条路径仍带污点
 * bind_url = c_semantics/control/goto_conditional_paths_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void goto_conditional_paths_T(int c) {
    char *p = taint_src();
    if (c) goto clean;
    goto done;
clean:
    p = "safe";
done:
    taint_sink(p);
}
