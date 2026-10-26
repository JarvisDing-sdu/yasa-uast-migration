/*
 * evaluation information start
 * real case = true
 * evaluation item = 结构体指针参数
 * scene introduction = 通过指针修改调用方结构体
 * bind_url = c_semantics/aggregate/struct_pointer_parameter_writes_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

static void mutate(struct S *s) { s->p = taint_src(); }
void struct_pointer_parameter_writes_T(void) {
    struct S s = { "safe" };
    mutate(&s);
    taint_sink(s.p);
}
