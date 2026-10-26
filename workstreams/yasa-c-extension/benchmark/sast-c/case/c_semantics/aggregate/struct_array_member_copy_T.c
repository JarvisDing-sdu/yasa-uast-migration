/*
 * evaluation information start
 * real case = true
 * evaluation item = 数组成员复制
 * scene introduction = 数组成员随结构体按值复制
 * bind_url = c_semantics/aggregate/struct_array_member_copy_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct Arr { char *v[2]; };

void struct_array_member_copy_T(void) {
    struct Arr a = { { taint_src(), "x" } };
    struct Arr b = a;
    a.v[0] = "safe";
    taint_sink(b.v[0]);
}
