/*
 * evaluation information start
 * real case = false
 * evaluation item = 结构体赋值
 * scene introduction = b = a 复制后污染 a
 * bind_url = c_semantics/aggregate/struct_assign_copy_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

void struct_assign_copy_F(void) {
    struct S a = { "safe" }, b = { "init" };
    b = a;
    a.p = taint_src();
    taint_sink(b.p);
}
