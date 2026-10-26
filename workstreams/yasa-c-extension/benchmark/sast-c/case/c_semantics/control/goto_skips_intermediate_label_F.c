/*
 * evaluation information start
 * real case = false
 * evaluation item = goto
 * scene introduction = goto 跳过中间标签
 * bind_url = c_semantics/control/goto_skips_intermediate_label_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
void goto_skips_intermediate_label_F(void) {
    goto done;
unused:
    taint_sink(taint_src());
done:
    return;
}
