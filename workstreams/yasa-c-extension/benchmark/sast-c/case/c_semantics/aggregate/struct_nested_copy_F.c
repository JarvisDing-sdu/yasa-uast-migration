/*
 * evaluation information start
 * real case = false
 * evaluation item = 嵌套结构体复制
 * scene introduction = 复制后污染源的内层字段
 * bind_url = c_semantics/aggregate/struct_nested_copy_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct In { char *p; };
struct Out { struct In in; char *other; };

void struct_nested_copy_F(void) {
    struct Out a = { { "safe" }, "x" };
    struct Out b = a;
    a.in.p = taint_src();
    taint_sink(b.in.p);
}
