/*
 * evaluation information start
 * real case = false
 * evaluation item = 数组成员复制
 * scene introduction = 复制后污染源的数组成员
 * bind_url = c_semantics/aggregate/struct_array_member_copy_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct Arr { char *v[2]; };

void struct_array_member_copy_F(void) {
    struct Arr a = { { "safe", "x" } };
    struct Arr b = a;
    a.v[0] = taint_src();
    taint_sink(b.v[0]);
}
