/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体赋值
 * scene introduction = b = a 复制后修改 a
 * bind_url = c_semantics/aggregate/struct_assign_copy_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

void struct_assign_copy_T(void) {
    struct S a = { taint_src() }, b = { "init" };
    b = a;
    a.p = "safe";
    taint_sink(b.p);
}
