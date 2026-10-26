/*
 * evaluation information start
 * real case = true
 * evaluation item = 按值传参
 * scene introduction = 被调函数读取按值传入的污点字段
 * bind_url = c_semantics/aggregate/struct_by_value_parameter_reads_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
char *taint_src(void);
void taint_sink(const char *s);
struct S { char *p; };

static void use(struct S s) { taint_sink(s.p); }
void struct_by_value_parameter_reads_T(void) {
    struct S s = { taint_src() };
    use(s);
}
