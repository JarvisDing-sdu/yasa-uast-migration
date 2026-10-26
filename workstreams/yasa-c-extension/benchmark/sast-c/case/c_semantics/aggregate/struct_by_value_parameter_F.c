/*
 * evaluation information start
 * real case = false
 * evaluation item = 按值传参
 * scene introduction = 被调函数修改形参副本不影响调用方
 * bind_url = c_semantics/aggregate/struct_by_value_parameter_F
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

static void mutate(struct S s) { s.p = taint_src(); }
void struct_by_value_parameter_F(void) {
    struct S s = { "safe" };
    mutate(s);
    taint_sink(s.p);
}
