/*
 * evaluation information start
 * real case = false
 * evaluation item = 结构体值复制
 * scene introduction = 复制后污染源结构体，不影响副本
 * bind_url = c_semantics/aggregate/struct_copy_no_alias_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

void struct_copy_no_alias_F(void) {
    struct S a = { "safe" };
    struct S b = a;
    a.p = taint_src();
    taint_sink(b.p);
}
