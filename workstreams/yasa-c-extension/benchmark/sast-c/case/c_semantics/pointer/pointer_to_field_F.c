/*
 * evaluation information start
 * real case = false
 * evaluation item = 字段地址
 * scene introduction = 通过字段地址写入不影响其它字段
 * bind_url = c_semantics/pointer/pointer_to_field_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct Two { char *a; char *b; };

void pointer_to_field_F(void) {
    struct Two s = { "safe", "safe" };
    char **pf = &s.a;
    *pf = taint_src();
    taint_sink(s.b);
}
