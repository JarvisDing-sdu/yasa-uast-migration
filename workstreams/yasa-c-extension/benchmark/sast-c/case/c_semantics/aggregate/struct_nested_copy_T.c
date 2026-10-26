/*
 * evaluation information start
 * real case = true
 * evaluation item = 嵌套结构体复制
 * scene introduction = 内层结构体按值复制
 * bind_url = c_semantics/aggregate/struct_nested_copy_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct In { char *p; };
struct Out { struct In in; char *other; };

void struct_nested_copy_T(void) {
    struct Out a = { { taint_src() }, "x" };
    struct Out b = a;
    a.in.p = "safe";
    taint_sink(b.in.p);
}
