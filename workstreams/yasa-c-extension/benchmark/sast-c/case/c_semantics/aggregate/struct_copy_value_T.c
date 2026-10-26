/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体值复制
 * scene introduction = 复制后修改源结构体，副本仍是原值
 * bind_url = c_semantics/aggregate/struct_copy_value_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

void struct_copy_value_T(void) {
    struct S a = { taint_src() };
    struct S b = a;
    a.p = "safe";
    taint_sink(b.p);
}
